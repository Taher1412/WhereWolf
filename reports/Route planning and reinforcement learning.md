# Routes away from danger: is reinforcement learning the right tool?

**Question.** Near now walks a wounded soldier back to the CCP, and plans the medic team's route to a casualty who can't walk. Both routes should avoid the danger zones on the map. Could reinforcement learning (RL) find better routes than what we built?

**Short answer.** Not for the route itself, and not this weekend.
- **What we know when a route is needed:** the street network (OSM) and the risk map (the danger zones).
- **What already solves that exactly:** for a known network and a known risk cost, the safest route is a shortest-path problem. Dijkstra solves it exactly, in about 30 ms on our 45,000-node walking network.
- **What RL would add:** it would learn an approximation of that same answer, needs a simulator and many training runs, and comes with no guarantee. A medic will ask "why did it send us there?". "The network learned it" is a weak answer; "this is the path with the least metres inside reported fire zones" is a strong one.

RL, or more precisely sequential decision-making under uncertainty (MDP and POMDP models), does become useful in four specific places. They are listed below in order of value for Near.

## What we built

The code is in `backend/route.py` and `backend/guide.py`.

- **Network.** Every way you can walk on in the cached OSM data: residential streets, footways, paths and tracks, plus primary to tertiary roads. Motorways and tunnels are left out.
  - Size: 45,565 nodes and 75,768 edges.
  - The graph is built in about 1 s at startup.
- **Cost of an edge.** Its length × (1 + risk).
  - Risk sums, over every placed danger zone: weight(type) × confidence × freshness × how far the edge is inside the zone.
  - The weights are placeholders to agree with a mentor: mines 200, sniper 40, small arms 30, armour 25, explosions 15, drone 8.
  - A weight of 30 means one metre under small-arms fire is worth 30 extra metres of walking.
- **Solver.** Dijkstra (scipy).
  - Each route is solved twice: once on the risk cost, and once on plain length. The difference gives what the map reports: "+390 m detour, avoids 398 m inside the small-arms zone" in the test scene.
- **Rerouting.** When a new zone appears, we check the rest of the walker's route.
  - If it now crosses danger and a safer route exists, the walker gets a new route and is told so.
  - If no safer route exists, the walker gets a spoken warning instead.
  - This is the standard "optimistic replanning" policy.
- **Guidance without GPS.**
  - The route is cut into legs at real turns.
  - Each leg is spoken with landmarks instead of street signs ("walk with the keep at your 2 o'clock, about 150 metres").
  - The pin moves by dead reckoning: the phone's step counter, or walking speed × time.
  - Its uncertainty circle grows with distance walked: 10 % with the step counter, 25 % on time alone.
  - Saying "next" at a turn puts the pin back on the junction and shrinks the circle.
  - A new landmark report re-locates the walker around the expected spot, and the route restarts from there.

## Where RL (or its planning cousins) would actually help

### 1. The walker doesn't know exactly where they are: plan over the uncertainty

**Today:** we plan from the single best position estimate and give instructions for it. If the estimate is 150 m off, "turn left at the junction" may be the wrong junction.

**Better:** treat the position as a probability map, which the localiser already gives us. Choose the instruction that works best *on average over that map*. This is a POMDP (partially observable Markov decision process).

**The cheap, standard approximation is QMDP:**
1. Compute the risk-weighted cost-to-go to the CCP from **every** cell of our 25 m grid. This is one Dijkstra run from the CCP: the "value function" in RL terms.
2. For each candidate instruction ("head toward the keep", "follow the main road east"), average the resulting cost-to-go over the position probabilities.
3. Pick the instruction with the lowest average.

QMDP assumes the uncertainty disappears after one step, so it is optimistic. It is still a big step up from planning on the single best guess. Learned versions exist (QMDP-net), but the plain algorithm needs no training.

**Effort:** about half a day. Everything it needs is already in the code: the grid, the probability heat map and the danger cost.

**This is the one to build next.** It is also an honest way to say "planning under uncertainty" in the pitch.

### 2. Threats are discovered on the way and they move

A drone zone ages out in 10 minutes. A sniper is only known once someone reports it. Routing when some roads may turn out to be blocked, and you only find out on arrival, is the **Canadian Traveller Problem**:
- Policies that hedge exist, and beat always replanning to the currently-best path.
- So do RL and probabilistic-inference formulations, such as policy search and multi-agent deep RL on graphs.
- The exact problem is intractable in general.

What we do now, replanning on every new report, is the standard baseline. A simple improvement with no training:
- add a "risk prior" around recent zones that grows with their age, since threats move;
- prefer routes with alternatives, so there is a way out if something new is reported.

### 3. Learning the risk weights instead of guessing them

The weights above are guesses. With after-action data, such as which routes medics actually took and where teams got hit, **inverse RL** could learn them. That data doesn't exist for this hackathon, so this is a partnership ask for the pitch, not a feature.

### 4. Dispatch: which team, when, with or without escort

This is where military RL work really is. Medical evacuation **dispatching** has been modelled as an MDP and solved with approximate dynamic programming and Q-learning:
- which helicopter or team goes to which casualty, and when;
- whether to send an armed escort;
- how to adapt when the battle changes.

It is a resource-allocation problem across many casualties and few teams, not a path problem. If Near grows to manage several medic teams, this is the right place for RL. The route planner above becomes the "travel time and risk" model that such a policy calls.

## Also worth doing without RL

- **Tail risk instead of average risk.** Minimise CVaR, the expected cost of the worst cases, rather than the expected cost. Medics care about the bad tail. CVaR shortest paths are solved with the same dynamic programming, no learning needed.
- **Cover.** Under trees, a walker is hidden from drones. The forest grid already knows the canopy share of each cell. Lowering the drone weight on wooded edges is one line of code, with a weight to validate.
- **Time windows.** "Mortar rounds every 10 minutes" turns into a time-dependent edge cost. That is still shortest-path, on a time-expanded graph.

## Limits to say out loud

- **Zone placement.** Zones are centred on the reporter, not the threat, because one phone can't locate a shooter. The detour avoids where reports came from, plus a safety radius.
- **Unplaced zones.** Zones from units located worse than ±500 m are not used for routing; we can't place them.
- **Dead reckoning drifts.** Without a confirmation at each turn, the pin's circle grows by a quarter of the distance walked, and the map shows it.
- **Placeholder numbers.** Walking speeds (1.1 m/s walking wounded, 0.6 m/s assisted) and step length (0.7 m) need checking on one real walk.

## Sources

- Deep RL for path planning, survey (2025): <https://arxiv.org/html/2507.15469v1>
- Risk-aware vs risk-calibrated UAV planning, review: <https://www.mdpi.com/2504-446X/10/5/351>
- DDPG path planning with circular no-go threat zones: <https://arxiv.org/pdf/2606.07855>
- Risk-averse autonomous systems, survey (risk measures, risk-averse RL): <https://arxiv.org/pdf/2109.08947>
- Risk-sensitive shortest paths with CVaR / EVaR: <https://arxiv.org/pdf/2103.14727>, <https://arxiv.org/html/2408.08668v1>
- Canadian Traveller Problem: <https://en.wikipedia.org/wiki/Canadian_traveller_problem>
  - High-quality policies: <https://gki.informatik.uni-freiburg.de/papers/eyerich-etal-psuws2010.pdf>
  - Probabilistic inference: <https://arxiv.org/pdf/1502.07314v1>
  - Multi-agent deep RL (MARVEL): <https://pdf.arxiv.org/pdf/2411.16134>
- QMDP-net (planning under partial observability): <https://www.comp.nus.edu.sg/%7Eleews/publications/NIPS17.pdf>
- SLAP, planning in belief space with replanning: <https://www.ri.cmu.edu/publications/slap-simultaneous-localization-and-planning-under-uncertainty-via-dynamic-replanning-in-belief-space>
- MEDEVAC dispatching as an MDP (Jenkins, AFIT): <https://apps.dtic.mil/sti/pdfs/AD1079716.pdf>
- RL for aeromedical evacuation in non-stationary combat (Kartchner, AFIT 2025): <https://scholar.afit.edu/etd/8259>
- Escort management with Q-learning (Gelbard, AFIT): <https://scholar.afit.edu/etd/5341>
- Multi-domain evacuation policies with RL/ADP (NATO STO): <https://review.sto.nato.int/images/Papers/STO-REVIEW-2023-01-SAS-ORA-02.pdf>
