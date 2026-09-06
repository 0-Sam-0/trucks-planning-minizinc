#!/usr/bin/env python3
"""
Trucks Problem Initial State Visualizer
----------------------------------------
Visualizes only the initial configuration of the problem without running MiniZinc.
"""

import sys
import re
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import argparse


class TrucksState:
    """Represents the state at a specific timestep"""
    def __init__(self, timestep):
        self.timestep = timestep
        self.truck_pos = None
        self.truck_contents = 0
        self.node_objects = {}
        self.load_from = None
        self.loaded = 0
        self.move_to = None
        self.unloaded = 0
        self.had_cross_e = 0


class TrucksInitVisualizer:
    """Visualizer for the trucks problem initial configuration"""
    
    def __init__(self, dzn_file):
        self.dzn_file = dzn_file
        self.initial_state = None
        
        # Problem data
        self.N = 0
        self.h = 0
        self.adj_matrix = None
        self.S_init = None
        self.T = None
        self.u = 0
        self.p = 0  # Initial truck position
        
        # Graph
        self.G = None
        self.pos = None
        
        # Matplotlib objects
        self.fig = None
        self.ax = None
        
    def _parse_dzn(self):
        """Parse the .dzn file to extract problem parameters"""
        print("=" * 80)
        print("PARSING .DZN FILE")
        print("=" * 80)
        
        with open(self.dzn_file, 'r') as f:
            content = f.read()
        
        # Extract N (number of nodes)
        match = re.search(r'N\s*=\s*(\d+)', content)
        if match:
            self.N = int(match.group(1))
            print(f"N (nodes): {self.N}")
        
        # Extract h (horizon)
        match = re.search(r'h\s*=\s*(\d+)', content)
        if match:
            self.h = int(match.group(1))
            print(f"h (horizon): {self.h}")
        
        # Extract adjacency matrix
        match = re.search(r'Adj\s*=\s*\[\|([^\]]+)\|\]', content, re.DOTALL)
        if match:
            matrix_str = match.group(1)
            rows = [line.strip() for line in matrix_str.split('|') if line.strip()]
            self.adj_matrix = []
            for row in rows:
                # Remove comments
                row_clean = re.sub(r'%.*$', '', row).strip()
                if row_clean:
                    values = [int(x.strip()) for x in row_clean.split(',') if x.strip()]
                    self.adj_matrix.append(values)
            self.adj_matrix = np.array(self.adj_matrix)
            print(f"Adjacency matrix: {self.adj_matrix.shape}")
        
        # Extract S_init (initial objects at nodes)
        match = re.search(r'S_init\s*=\s*\[([^\]]+)\]', content)
        if match:
            self.S_init = [int(x.strip()) for x in match.group(1).split(',')]
            print(f"S_init: {self.S_init}")
        
        # Extract T (target nodes)
        match = re.search(r'T\s*=\s*\[([^\]]+)\]', content)
        if match:
            self.T = [int(x.strip()) for x in match.group(1).split(',')]
            print(f"T (targets): {self.T}")
        
        # Extract u (initial truck position)
        match = re.search(r'u\s*=\s*(\d+)', content)
        if match:
            self.u = int(match.group(1))
            print(f"u (initial truck position): {self.u}")

        # Extract p (truck capacity)
        match = re.search(r'p\s*=\s*(\d+)', content)
        if match:
            self.p = int(match.group(1))
            print(f"p (truck capacity): {self.p}")
        
        print("=" * 80 + "\n")
    
    def _create_initial_state(self):
        """Create initial state from parsed data"""
        self.initial_state = TrucksState(0)
        self.initial_state.truck_pos = self.u
        self.initial_state.truck_contents = 0
        
        # Set initial node objects
        for i in range(self.N):
            if self.S_init[i] > 0:
                self.initial_state.node_objects[i + 1] = self.S_init[i]
    
    def _build_graph(self):
        """Build NetworkX graph from adjacency matrix"""
        self.G = nx.Graph()
        
        # Add nodes
        for i in range(1, self.N + 1):
            self.G.add_node(i)
        
        # Add edges
        for i in range(self.N):
            for j in range(i + 1, self.N):
                if self.adj_matrix[i][j] == 1:
                    self.G.add_edge(i + 1, j + 1)
        
        # Calculate layout
        self.pos = nx.spring_layout(self.G, k=2, iterations=50, seed=42)
    
    def _get_node_color(self, node_id):
        """Determine node color based on its role"""
        # Target nodes - green
        if self.T[node_id - 1] == 1:
            return '#50C878'  # Green
        
        # Initial source nodes - light red
        if self.S_init[node_id - 1] > 0:
            return '#FFB6C1'  # Light pink/red
        
        # Normal nodes - gray
        return '#CCCCCC'  # Gray
    
    def _draw_initial_state(self):
        """Draw the initial graph state"""
        self.ax.clear()
        
        # Draw all edges in gray
        nx.draw_networkx_edges(self.G, self.pos, ax=self.ax, 
                              edge_color='#999999', width=2, alpha=0.6)
        
        # Draw nodes with colors
        node_colors = [self._get_node_color(node) for node in self.G.nodes()]
        nx.draw_networkx_nodes(self.G, self.pos, ax=self.ax,
                              node_color=node_colors, node_size=800,
                              edgecolors='black', linewidths=2)
        
        # Draw node labels (node ID)
        node_labels = {node: str(node) for node in self.G.nodes()}
        nx.draw_networkx_labels(self.G, self.pos, node_labels, ax=self.ax,
                               font_size=12, font_weight='bold')
        
        # Draw object counts on nodes
        for node in self.G.nodes():
            count = self.initial_state.node_objects.get(node, 0)
            if count > 0:
                x, y = self.pos[node]
                self.ax.text(x, y - 0.17, f'OBJ: {count}', 
                           ha='center', va='top', fontsize=9,
                           bbox=dict(boxstyle='round,pad=0.3', 
                                   facecolor='yellow', alpha=0.8,
                                   edgecolor='black', linewidth=1))
        
        # Draw truck as a symbol above the node
        if self.initial_state.truck_pos:
            x, y = self.pos[self.initial_state.truck_pos]
            
            # Draw truck as a rectangle
            truck_width = 0.12
            truck_height = 0.08
            truck = FancyBboxPatch((x - truck_width/2, y + 0.13), 
                                   truck_width, truck_height,
                                   boxstyle="round,pad=0.01",
                                   facecolor='#4A90E2', edgecolor='black', 
                                   linewidth=2, zorder=10)
            self.ax.add_patch(truck)
            
            # Label "TRUCK"
            self.ax.text(x, y + 0.17, 'T', 
                       ha='center', va='center', fontsize=10,
                       color='white', weight='bold', zorder=11)
            
            # Show load (empty at start)
            self.ax.text(x + 0.08, y + 0.2, f'[{self.initial_state.truck_contents}]', 
                       ha='left', va='center', fontsize=9,
                       color='red', weight='bold',
                       bbox=dict(boxstyle='round,pad=0.2', 
                               facecolor='white', alpha=0.9,
                               edgecolor='red', linewidth=1.5))
        
        # Title
        title = 'Initial Configuration (t=0)'
        title += f'\n\nTruck at node {self.initial_state.truck_pos}'
        title += f' | Initial position: {self.u}'
        title += f' | Capacity: {self.p}'
        title += f' | Horizon: {self.h}'
        
        # Count total objects to deliver
        total_objects = sum(self.S_init)
        target_nodes = sum(self.T)
        title += f'\n{total_objects} objects to deliver to {target_nodes} target nodes'
        
        self.ax.set_title(title, fontsize=12, weight='bold', pad=20)
        
        # Legend
        legend_elements = [
            plt.Line2D([0], [0], marker='s', color='w', 
                      markerfacecolor='#4A90E2', markersize=10, label='Truck'),
            plt.Line2D([0], [0], marker='o', color='w', 
                      markerfacecolor='#50C878', markersize=10, label='Target Node'),
            plt.Line2D([0], [0], marker='o', color='w', 
                      markerfacecolor='#FFB6C1', markersize=10, label='Initial Source (with objects)'),
            plt.Line2D([0], [0], marker='o', color='w', 
                      markerfacecolor='#CCCCCC', markersize=10, label='Normal Node')
        ]
        self.ax.legend(handles=legend_elements, loc='upper left', fontsize=9)
        
        self.ax.axis('off')
        self.fig.canvas.draw_idle()
    
    def visualize(self):
        """Create visualization of initial state"""
        print("=" * 80)
        print("VISUALIZING INITIAL CONFIGURATION")
        print("=" * 80)
        print("This shows the problem setup without running MiniZinc.")
        print("=" * 80 + "\n")
        
        # Parse data file
        self._parse_dzn()
        
        # Create initial state
        self._create_initial_state()
        
        # Build graph
        self._build_graph()
        
        # Create figure and axes
        self.fig = plt.figure(figsize=(14, 10))
        self.ax = plt.subplot(111)
        
        # Draw initial state
        self._draw_initial_state()
        
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Visualize initial configuration of Trucks Problem (no MiniZinc execution)'
    )
    parser.add_argument('dzn_file', help='Path to .dzn file')
    
    args = parser.parse_args()
    
    visualizer = TrucksInitVisualizer(args.dzn_file)
    visualizer.visualize()


if __name__ == '__main__':
    main()
