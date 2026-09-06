% ============================================================================
% 16 TRUCKS PROBLEM - COST MINIMIZATION
% ============================================================================
%
% Problem Description:
% -------------------
% A truck driver must move h identical objects from source nodes S to target 
% nodes T on an undirected connected graph G=(V,E). The truck can hold at most 
% 2 objects simultaneously. The driver starts at node u.
% 
% This version minimizes the total travel cost for a plan of fixed length k.
% The value of k is determined by the SAT version (trucks_optimized.mzn).
%
% Cost Model:
% - Cross_E (empty teleport): cost = Dist[origin, destination]
% - Cross_K (loaded move): cost = Dist[origin, destination] * cross_k_weight
% - Total cost = sum of all Cross_E costs + sum of all Cross_K costs
% 
% Key constraints and requirements:
% - Each timestep represents one Cross_K (movement with at least 1 object loaded)
% - Action sequence per timestep: Cross_E* -> L* -> Cross_K -> U*
% - Cross_E*: traverse empty (0+ times, only if truck empty)
% - L*: load objects (1+ if Cross_E done, 0+ otherwise)
% - Cross_K: traverse with load (mandatory, exactly 1 per timestep)
% - U*: unload objects (0+ times, mandatory if arrive with 2 on occupied node)
% - Special rule: if arrive with 2 objects on occupied node, must unload >=1
%   and cannot leave next timestep with 2 objects loaded
% - Goal must be reached EXACTLY at timestep k (not before)
%
% Problem Parameters:
% ------------------
% - N: number of nodes in the graph
% - h: number of objects to transport
% - k: exact plan length (number of Cross_K operations) - found by SAT version
% - Adj: adjacency matrix of the graph
% - Dist: distance matrix (shortest paths between all node pairs)
% - S_init: initial object distribution on nodes
% - T: set of target nodes (each must have >=1 objects at end)
% - u: initial position of the truck driver
% - cross_k_weight: multiplicative weight for Cross_K costs (hardcoded = 2)
%
% ============================================================================

% ============================================================================
% PARAMETERS (Input values that define the problem instance)
% ============================================================================

% Number of nodes in the graph
int: N;

% Number of objects to transport
int: h;

% Exact plan length (number of timesteps / Cross_K operations)
int: k;

% Adjacency matrix: Adj[i,j] = 1 if edge (i,j) exists, 0 otherwise
array[1..N, 1..N] of 0..1: Adj;

% Distance matrix: Dist[i,j] = shortest path distance from node i to node j
% Used for both Cross_E (teleport) and Cross_K (loaded move) costs
array[1..N, 1..N] of int: Dist;

% Initial object distribution: S_init[i] = number of objects at node i initially
array[1..N] of int: S_init;

% Target nodes: T[i] = 1 if node i is a target, 0 otherwise
array[1..N] of 0..1: T;

% Initial position of the truck driver
1..N: u;

% Multiplicative weight for Cross_K (loaded move) costs
int: cross_k_weight = 2;

% ============================================================================
% SETS (Ranges of valid values for indices)
% ============================================================================

% Node indices (1..N for nodes, 0 for truck)
set of int: NODES = 1..N;

% Extended index set including truck position
set of int: WORLD_INDEX = 0..N;

% Timestep indices
set of int: TIMESTEPS = 0..k;

% ============================================================================
% DECISION VARIABLES (Values the solver must determine)
% ============================================================================

% ----------------------------------------------------------------------------
% PRIMARY DECISION VARIABLE: World Matrix
% ----------------------------------------------------------------------------
% World[i, t] represents the state of the world at timestep t
% 
% Dimensions:
%   - First index (0..N): 0 = truck contents, 1..N = node contents
%   - Second index (0..k): timestep
% 
% Value: number of objects
%   - World[0, t] in {0,1,2}: objects in truck at timestep t
%   - World[i, t] >= 0: objects at node i at timestep t

array[WORLD_INDEX, TIMESTEPS] of var 0..h: World;

% ----------------------------------------------------------------------------
% PRIMARY DECISION VARIABLE: Truck Position
% ----------------------------------------------------------------------------
% Spos[t] = node where the truck is located at timestep t
%
% Dimensions:
%   - Index (0..k): timestep
%
% Value: node index (1..N)

array[TIMESTEPS] of var NODES: Spos;

% ----------------------------------------------------------------------------
% AUXILIARY VARIABLES (Helper variables for constraints)
% ----------------------------------------------------------------------------
% load_node[t] = node where loading L* happens at timestep t
%
% Dimensions:
%   - Index (1..k): timestep (not needed for t=0)
%
% Value: node index (1..N)

array[1..k] of var NODES: load_node;

% loaded[t] = number of objects loaded during L* at timestep t
%
% Dimensions:
%   - Index (1..k): timestep
%
% Value: 0..2 (cannot load more than truck capacity)

array[1..k] of var 0..2: loaded;

% unloaded[t] = number of objects unloaded during U* at timestep t
%
% Dimensions:
%   - Index (1..k): timestep
%
% Value: 0..2 (cannot unload more than truck capacity)

array[1..k] of var 0..2: unloaded;

% truck_after_load[t] = truck contents after L* but before Cross_K at timestep t
%
% Dimensions:
%   - Index (1..k): timestep
%
% Value: 0..2 (truck capacity)

array[1..k] of var 0..2: truck_after_load;

% had_cross_e[t] = 1 if Cross_E* was performed at timestep t, 0 otherwise
%
% Dimensions:
%   - Index (1..k): timestep
%
% Value:
%   - 1: truck was empty and moved to a different node for loading
%   - 0: truck was already loaded, so load_node = Spos[t-1]

array[1..k] of var 0..1: had_cross_e;

% ----------------------------------------------------------------------------
% COST TRACKING VARIABLES
% ----------------------------------------------------------------------------
% cross_e_cost[t] = cost of Cross_E* teleport at timestep t
% Value: Dist[Spos[t-1], load_node[t]] if had_cross_e[t]=1, otherwise 0

array[1..k] of var 0..max(Dist): cross_e_cost;

% cross_k_cost[t] = cost of Cross_K (loaded move) at timestep t
% Value: Dist[load_node[t], Spos[t]] * cross_k_weight

array[1..k] of var 0..max(Dist)*cross_k_weight: cross_k_cost;

% total_cross_e_cost = sum of all Cross_E costs

var 0..sum(Dist)*k: total_cross_e_cost;

% total_cross_k_cost = sum of all Cross_K costs

var 0..sum(Dist)*cross_k_weight*k: total_cross_k_cost;

% total_cost = objective to minimize (sum of all costs)

var 0..sum(Dist)*(1+cross_k_weight)*k: total_cost;

% ============================================================================
% CONSTRAINTS (Rules that must be satisfied)
% ============================================================================

% ----------------------------------------------------------------------------
% CONSTRAINT 1: Initial State
% ----------------------------------------------------------------------------
% 
% Explanation:
% The world must start in the configuration specified by the input parameters.
% The truck is empty, positioned at node u, and objects are distributed according
% to S_init.

constraint World[0, 0] = 0;
constraint Spos[0] = u;
constraint forall(i in NODES)(World[i, 0] = S_init[i]);

% ----------------------------------------------------------------------------
% CONSTRAINT 2: Goal State at Timestep k
% ----------------------------------------------------------------------------
%
% Explanation:
% The goal must be reached EXACTLY at timestep k. All objects must be in target
% nodes T, the truck must be empty, and each target node must have at least one
% object. This is simpler than the previous plan_length approach since we now
% search for solutions of exact length k.

constraint World[0, k] = 0;
constraint forall(i in NODES where T[i] = 1)(World[i, k] >= 1);
constraint sum(i in NODES where T[i] = 1)(World[i, k]) = h;
constraint forall(i in NODES where T[i] = 0)(World[i, k] = 0);

% ----------------------------------------------------------------------------
% CONSTRAINT 3: Conservation of Objects
% ----------------------------------------------------------------------------
%
% Explanation:
% Objects are never created or destroyed, only moved between nodes and the truck.
% The total number of objects in the system must always equal h.

constraint forall(t in TIMESTEPS)(
    sum(i in WORLD_INDEX)(World[i, t]) = h
);

% ----------------------------------------------------------------------------
% CONSTRAINT 4: Truck Capacity
% ----------------------------------------------------------------------------
%
% Explanation:
% The truck can hold at most 2 objects at any time.

constraint forall(t in TIMESTEPS)(World[0, t] <= 2);

% ----------------------------------------------------------------------------
% CONSTRAINT 5: Truck After Load Calculation
% ----------------------------------------------------------------------------
%
% Explanation:
% Computes the truck contents after loading L* but before Cross_K.
% This is the sum of what was in the truck at t-1 plus what was loaded.

constraint forall(t in 1..k)(
    truck_after_load[t] = World[0, t-1] + loaded[t]
);

constraint forall(t in 1..k)(
    truck_after_load[t] >= 1 /\ truck_after_load[t] <= 2
);

% ----------------------------------------------------------------------------
% CONSTRAINT 6: Cross_E and Load Node Selection
% ----------------------------------------------------------------------------
%
% Explanation:
% If the truck is empty at t-1, it can perform Cross_E* to reach any node
% with objects. If the truck already has objects, load_node must be Spos[t-1].

constraint forall(t in 1..k)(
    (World[0, t-1] = 0) -> (had_cross_e[t] = 1)
);

constraint forall(t in 1..k)(
    (World[0, t-1] > 0) -> (had_cross_e[t] = 0 /\ load_node[t] = Spos[t-1])
);

% If Cross_E was done, must load at least 1 object

constraint forall(t in 1..k)(
    (had_cross_e[t] = 1) -> (loaded[t] >= 1)
);

% ----------------------------------------------------------------------------
% CONSTRAINT 7: Cross_K Adjacency
% ----------------------------------------------------------------------------
%
% Explanation:
% Cross_K moves the truck from load_node[t] to Spos[t]. This movement must
% follow an edge in the graph, i.e., Adj[load_node[t], Spos[t]] = 1.

constraint forall(t in 1..k)(
    Adj[load_node[t], Spos[t]] = 1
);

% ----------------------------------------------------------------------------
% CONSTRAINT 8: Loading from Load Node
% ----------------------------------------------------------------------------
%
% Explanation:
% When loading objects at load_node[t], the node must have enough objects
% available. The node's object count at timestep t-1 must be >= loaded[t].

constraint forall(t in 1..k)(
    World[load_node[t], t-1] >= loaded[t]
);

% ----------------------------------------------------------------------------
% CONSTRAINT 9: State Transition - Load Node
% ----------------------------------------------------------------------------
%
% Explanation:
% The load_node loses the objects that were loaded onto the truck.
% Its object count decreases by loaded[t] from timestep t-1 to t.

constraint forall(t in 1..k)(
    World[load_node[t], t] = World[load_node[t], t-1] - loaded[t]
);

% ----------------------------------------------------------------------------
% CONSTRAINT 10: State Transition - Destination Node
% ----------------------------------------------------------------------------
%
% Explanation:
% The destination node Spos[t] receives the objects that were unloaded.
% In the current model, we enforce that Spos[t] != load_node[t] for all
% timesteps, meaning loading and unloading always happen at different nodes.

constraint forall(t in 1..k)(
	Spos[t] != load_node[t]
);

constraint forall(t in 1..k)(
	World[Spos[t], t] = World[Spos[t], t-1] + unloaded[t]
);

% ----------------------------------------------------------------------------
% CONSTRAINT 11: State Transition - Unchanged Nodes
% ----------------------------------------------------------------------------
%
% Explanation:
% Nodes that are neither load_node[t] nor Spos[t] are not affected by the
% actions at timestep t. Their object counts remain unchanged.

constraint forall(t in 1..k, i in NODES)(
    (i != load_node[t] /\ i != Spos[t]) -> (World[i, t] = World[i, t-1])
);

% ----------------------------------------------------------------------------
% CONSTRAINT 12: State Transition - Truck Contents
% ----------------------------------------------------------------------------
%
% Explanation:
% The truck's contents at timestep t equals what it had after loading minus
% what was unloaded at the destination.

constraint forall(t in 1..k)(
    World[0, t] = truck_after_load[t] - unloaded[t]
);

% ----------------------------------------------------------------------------
% CONSTRAINT 13: Unloading Limits
% ----------------------------------------------------------------------------
%
% Explanation:
% Cannot unload more objects than the truck contains after loading.

constraint forall(t in 1..k)(
    unloaded[t] <= truck_after_load[t]
);

% ----------------------------------------------------------------------------
% CONSTRAINT 14: Mandatory Unload Rule (REIFIED VERSION)
% ----------------------------------------------------------------------------
%
% Explanation:
% Special rule: if the truck arrives with 2 objects at a node that already
% contains objects (before unloading), it MUST unload at least 1 object.
% Additionally, at the next timestep, it cannot have 2 objects loaded again
% (this prevents "passing through" with full truck).

array[1..k] of var bool: must_unload;

constraint forall(t in 1..k)(
    must_unload[t] -> (unloaded[t] >= 1 /\ World[0, t] < 2)
);

constraint forall(t in 1..k)(
    must_unload[t] <-> (
        truck_after_load[t] = 2 /\ 
        World[Spos[t], t-1] > 0
    )
);

constraint forall(t in 1..k-1)(
    must_unload[t] -> (truck_after_load[t+1] < 2)
);

% ----------------------------------------------------------------------------
% CONSTRAINT 15: Prevent Redundant Unload-Load Cycles
% ----------------------------------------------------------------------------
%
% Explanation:
% This constraint prevents a specific type of inefficient move sequence:
% unloading objects at a node at timestep t, and then loading objects from
% that same node at timestep t+1. Such sequences are redundant and wasteful
% since objects are being moved off and then immediately back onto the truck
% at the same location.

constraint forall(t in 1..k-1)(
    not (unloaded[t] > 0 /\ load_node[t+1] == Spos[t] /\ loaded[t+1] > 0)
);

% ----------------------------------------------------------------------------
% COST CALCULATION CONSTRAINTS
% ----------------------------------------------------------------------------

% Cross_E cost: distance traveled when teleporting empty
% If had_cross_e[t] = 1: cost = Dist[Spos[t-1], load_node[t]]
% If had_cross_e[t] = 0: cost = 0 (no teleport, truck stays at same node)

constraint forall(t in 1..k)(
    cross_e_cost[t] = Dist[Spos[t-1], load_node[t]]
);

% Cross_K cost: distance traveled when moving with loaded truck
% Cost = Dist[load_node[t], Spos[t]] * cross_k_weight

constraint forall(t in 1..k)(
    cross_k_cost[t] = Dist[load_node[t], Spos[t]] * cross_k_weight
);

% Total costs calculation

constraint total_cross_e_cost = sum(t in 1..k)(cross_e_cost[t]);
constraint total_cross_k_cost = sum(t in 1..k)(cross_k_cost[t]);
constraint total_cost = total_cross_e_cost + total_cross_k_cost;

% ============================================================================
% SEARCH STRATEGY
% ============================================================================

solve :: seq_search([
           seq_search([
             int_search([Spos[t]], input_order, indomain_min),
             int_search([load_node[t]], first_fail, indomain_min),
             int_search([loaded[t]], first_fail, indomain_min),
             int_search([unloaded[t]], first_fail, indomain_min),
             int_search([World[i,t] | i in WORLD_INDEX], first_fail, indomain_min)
           ]) | t in 1..k
         ])
      minimize total_cost;

% ============================================================================
% OUTPUT FORMATTING
% ============================================================================

output [
    "=== TRUCKS PROBLEM SOLUTION - COST MINIMIZATION (k=", show(k), ") ===\n\n",
    "Initial state (t=0):\n",
    "  Truck at node: ", show(Spos[0]), " (contents: ", show(World[0,0]), ")\n",
    "  Nodes: [" ++ concat([show(i) ++ ":" ++ show(World[i,0]) ++ if i < N then ", " else "" endif | i in NODES]) ++ "]\n\n"
] ++
[
    "Timestep " ++ show(t) ++ ":\n" ++
    "  Load from: " ++ show(load_node[t]) ++ 
    ", Loaded: " ++ show(loaded[t]) ++ 
    ", Cross_E: " ++ show(had_cross_e[t]) ++ "\n" ++
    "  Cross_E cost: " ++ show(cross_e_cost[t]) ++
    " (from node " ++ show(Spos[t-1]) ++ " to " ++ show(load_node[t]) ++ ")\n" ++
    "  Move to: " ++ show(Spos[t]) ++ 
    ", Unloaded: " ++ show(unloaded[t]) ++ "\n" ++
    "  Cross_K cost: " ++ show(cross_k_cost[t]) ++ 
    " (from node " ++ show(load_node[t]) ++ " to " ++ show(Spos[t]) ++ ", weight=" ++ show(cross_k_weight) ++ ")\n" ++
    "  Truck at node: " ++ show(Spos[t]) ++ 
    " (contents: " ++ show(World[0,t]) ++ ")\n" ++
    "  Nodes: [" ++ concat([show(i) ++ ":" ++ show(World[i,t]) ++ if i < N then ", " else "" endif | i in NODES]) ++ "]\n\n"
    | t in 1..k
] ++ [
    "=== GOAL REACHED AT TIMESTEP k=", show(k), " ===\n",
    "All ", show(h), " objects are now in target nodes:\n"
] ++ [
    "  Node " ++ show(i) ++ ": " ++ show(World[i,k]) ++ " objects\n"
    | i in NODES where T[i] = 1
] ++ [
    "\n=== COST SUMMARY ===\n",
    "Total Cross_E cost: ", show(total_cross_e_cost), "\n",
    "Total Cross_K cost: ", show(total_cross_k_cost), "\n",
    "TOTAL COST: ", show(total_cost), "\n"
];

%-----------------------------------------------------------------------------
%-----------------------------------------------------------------------------

%-----------------------------------------------------------------------------
%-----------------------------------------------------------------------------