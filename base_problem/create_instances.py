#!/usr/bin/env python3
"""
Instance Generator for the Trucks Problem
Generates benchmark datasets according to the project specifications.
"""

import random
import os
from pathlib import Path
from typing import List, Tuple, Set
import argparse


def generate_connected_graph(n: int) -> List[List[int]]:
    """
    Generate a random connected undirected graph with n nodes.
    Uses a modified random graph approach ensuring connectivity.

    Args:
        n: Number of nodes in the graph

    Returns:
        Adjacency matrix as a 2D list
    """
    # Initialize adjacency matrix
    adj = [[0] * n for _ in range(n)]

    # First, create a spanning tree to ensure connectivity
    # Start with node 0 and randomly add edges to unconnected nodes
    connected = {0}
    unconnected = set(range(1, n))

    while unconnected:
        # Pick a random connected node
        from_node = random.choice(sorted(list(connected)))
        # Pick a random unconnected node
        to_node = random.choice(sorted(list(unconnected)))

        # Add edge
        adj[from_node][to_node] = 1
        adj[to_node][from_node] = 1

        # Update sets
        connected.add(to_node)
        unconnected.remove(to_node)

    # Add additional random edges (about 20% more edges)
    additional_edges = int(n * 0.4)
    for _ in range(additional_edges):
        i, j = random.sample(range(n), 2)
        if i != j:
            adj[i][j] = 1
            adj[j][i] = 1

    return adj


def get_neighbors(node: int, adj: List[List[int]]) -> List[int]:
    """Get all neighbors of a node."""
    return [i for i in range(len(adj)) if adj[node][i] == 1]


def simulate_random_movements(n: int, h: int, target_nodes: List[int],
                              adj: List[List[int]], k: int) -> Tuple[List[int], int, List[str]]:
    """
    Start from a consistent solution (all objects at target nodes)
    and simulate k random movements backwards to create initial state.

    New logic:
    - Each iteration: choose a node with objects (priority to targets)
    - Choose a random edge avoiding targets (if possible) and avoiding 
      the node from which the last object arrived (if possible)
    - Track last incoming node for each node

    Args:
        n: Number of nodes
        h: Number of objects
        target_nodes: List of target node indices
        adj: Adjacency matrix
        k: Number of random movements to simulate

    Returns:
        Tuple of (initial_object_distribution, initial_truck_position, trace)
    """
    trace = []
    trace.append(f"% --- GENERATION TRACE (Backwards from Target) ---")

    # Start with all objects distributed among target nodes
    obj_at_nodes = [0] * n

    # First, place one object on each target node
    for target_node in target_nodes:
        obj_at_nodes[target_node] += 1

    # Distribute remaining objects randomly among target nodes
    remaining_objects = h - len(target_nodes)
    for i in range(remaining_objects):
        target_node = random.choice(target_nodes)
        obj_at_nodes[target_node] += 1

    trace.append(f"% Initial distribution (all on targets): {obj_at_nodes}")

    # Track last incoming node for each node
    last_incoming_node = [None] * n

    for step in range(k):
        # Find nodes with objects
        targets_with_objects = [i for i in target_nodes if obj_at_nodes[i] > 0]
        non_targets_with_objects = [i for i in range(
            n) if i not in target_nodes and obj_at_nodes[i] > 0]

        candidates = None
        from_node = None

        while targets_with_objects or non_targets_with_objects:
            # Choose source node (priority to targets)
            if targets_with_objects:
                from_node = random.choice(targets_with_objects)
                trace.append(
                    f"% Step {step+1}: Selected target node {from_node+1} (has {obj_at_nodes[from_node]} objects)")
            elif non_targets_with_objects:
                from_node = random.choice(non_targets_with_objects)
                trace.append(
                    f"% Step {step+1}: Selected non-target node {from_node+1} (has {obj_at_nodes[from_node]} objects)")
            else:
                trace.append(
                    f"% Step {step+1}: No objects to move, stopping early")
                break

            # Get all neighbors
            neighbors = get_neighbors(from_node, adj)

            if not neighbors:   # not necessary due to connectivity, but just in case
                trace.append(
                    f"% Step {step+1}: Node {from_node+1} has no neighbors, skipping")
                continue

            # Filter 1: Avoid targets if possible
            non_target_neighbors = [
                n for n in neighbors if n not in target_nodes]

            if non_target_neighbors:
                candidates = non_target_neighbors
                break
            elif from_node in targets_with_objects:
                targets_with_objects.remove(from_node)
            elif from_node in non_targets_with_objects:
                non_targets_with_objects.remove(from_node)

            from_node = None

        if from_node is None:
            trace.append(
                f"% Step {step+1}: No valid source node found, stopping early")
            break

        # Filter 2: Avoid last incoming node if possible
        if last_incoming_node[from_node] is not None:
            candidates_no_backtrack = [
                n for n in candidates if n != last_incoming_node[from_node]]
            if candidates_no_backtrack:
                candidates = candidates_no_backtrack
                trace.append(
                    f"% Step {step+1}: Avoiding backtrack to node {last_incoming_node[from_node]+1}")

        # Choose destination
        to_node = random.choice(candidates)

        # Move object
        obj_at_nodes[from_node] -= 1
        obj_at_nodes[to_node] += 1

        # Update last incoming node
        last_incoming_node[to_node] = from_node

        trace.append(
            f"% Step {step+1}: Moved object {from_node+1} -> {to_node+1}")
        trace.append(f"% Step {step+1}: Distribution: {obj_at_nodes}")

    # Choose random starting position for truck
    start_pos = random.randint(0, n - 1)
    trace.append(f"% Truck starting position: {start_pos+1}")

    return obj_at_nodes, start_pos, trace


def generate_instance(n: int, config_idx: int, k: int, instance_idx: int) -> dict:
    """
    Generate a single instance of the trucks problem.

    Args:
        n: Number of nodes
        config_idx: Configuration index (0-3)
        k: Number of movements to simulate
        instance_idx: Instance index for naming

    Returns:
        Dictionary with instance data
    """
    # Generate connected graph
    adj = generate_connected_graph(n)

    # Calculate number of objects (h ≈ n/5)
    h = (n // 5) + 1

    # Choose target nodes (|T| ≈ 3..6, but must be ≤ h)
    # Each target node must have at least one object
    num_targets = random.randint(max(1, min(3, h)), min(6, h, n - 1))
    target_nodes_idx = random.sample(range(n), num_targets)
    target_nodes_bool = [1 if i in target_nodes_idx else 0 for i in range(n)]

    # Simulate random movements to create initial state
    obj_distribution, start_pos, trace = simulate_random_movements(
        n, h, target_nodes_idx, adj, k
    )

    return {
        'N': n,
        'h': h,
        'k': k,
        'Adj': adj,
        'S_init': obj_distribution,
        'T': target_nodes_bool,
        'u': start_pos + 1,  # MiniZinc uses 1-based indexing
        'instance_name': f'instance_n{n}_c{config_idx}_k{k}_i{instance_idx}',
        'trace': trace
    }


def write_dzn_file(instance: dict, output_path: str):
    """
    Write instance data to a .dzn file in MiniZinc format.

    Args:
        instance: Dictionary with instance data
        output_path: Path where to save the .dzn file
    """
    with open(output_path, 'w') as f:
        f.write(f"% {instance['instance_name']}.dzn\n")
        f.write(f"% Generated instance for the Trucks problem\n")
        f.write(
            f"% N={instance['N']}, h={instance['h']}, k={instance['k']}\n\n")

        f.write(f"% Number of nodes\n")
        f.write(f"N = {instance['N']};\n\n")

        f.write(f"% Number of objects\n")
        f.write(f"h = {instance['h']};\n\n")

        f.write(f"% Maximum plan length\n")
        f.write(f"%k = {instance['k']};\n\n")

        f.write(
            f"% Adjacency matrix (0-based internal, will be converted to 1-based)\n")
        f.write(f"Adj = [")
        for i, row in enumerate(instance['Adj']):
            if i == 0:
                f.write("|")
            else:
                f.write("      |")
            f.write(", ".join(map(str, row)))
            if i < len(instance['Adj']) - 1:
                f.write("\n")
        f.write("\n      |];\n\n")

        f.write(f"% Initial object distribution\n")
        f.write(f"S_init = [")
        f.write(", ".join(map(str, instance['S_init'])))
        f.write("];\n\n")

        f.write(f"% Target nodes (1 if target, 0 otherwise)\n")
        f.write(f"T = [")
        f.write(", ".join(map(str, instance['T'])))
        f.write("];\n\n")

        f.write(f"% Initial truck position (1-based indexing)\n")
        f.write(f"u = {instance['u']};\n\n")

        f.write("% --- DEBUG TRACE ---\n")
        for line in instance['trace']:
            f.write(f"{line}\n")


def generate_all_instances(output_dir: str = "instances"):
    """
    Generate all 100 instances according to specifications:
    - 5 graph sizes: |V| = 10, 14, 18, 22, 26
    - 4 configurations for each size
    - 5 k values: 5, 8, 11, 14, 17
    Total: 5 × 4 × 5 = 100 instances
    """
    Path(output_dir).mkdir(exist_ok=True)

    node_counts = [10, 14, 18, 22, 26]
    k_values = [5, 8, 11, 14, 17]

    instance_count = 0

    for n in node_counts:
        for config_idx in range(4):
            for k in k_values:
                instance = generate_instance(n, config_idx, k, instance_count)

                filename = f"{instance['instance_name']}.dzn"
                filepath = os.path.join(output_dir, filename)

                write_dzn_file(instance, filepath)

                instance_count += 1
                print(f"Generated {instance_count}/100: {filename}")

    print(
        f"\n✓ Successfully generated all 100 instances in '{output_dir}/' directory")


def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Generate instances for the Trucks problem'
    )
    parser.add_argument(
        '-o', '--output',
        default='instances',
        help='Output directory for generated instances (default: instances)'
    )
    parser.add_argument(
        '-s', '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        print(f"Using random seed: {args.seed}")

    generate_all_instances(args.output)


if __name__ == "__main__":
    main()
