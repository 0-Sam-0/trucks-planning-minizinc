#!/usr/bin/env python3
"""
Trucks Problem Visualizer
--------------------------
Executes MiniZinc and creates an interactive visualization of the solution.
The user can navigate through timesteps using buttons or keyboard arrows.
"""

import argparse
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.widgets import Button
import matplotlib.pyplot as plt
import subprocess
import sys
import re
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use('TkAgg')


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
        self.had_cross_e = 0  # Epsilon transition flag


class TrucksVisualizer:
    """Interactive visualizer for the trucks problem solution"""

    def __init__(self, mzn_file, dzn_file, k):
        self.mzn_file = mzn_file
        self.dzn_file = dzn_file
        self.k = k
        self.states = []
        self.current_step = 0

        # Problem data
        self.N = 0
        self.h = 0
        self.adj_matrix = None
        self.S_init = None
        self.T = None
        self.u = 0

        # Graph
        self.G = None
        self.pos = None

        # Matplotlib objects
        self.fig = None
        self.ax = None
        self.btn_next = None
        self.btn_prev = None
        self.btn_first = None
        self.btn_last = None

    def run_minizinc(self):
        """Execute MiniZinc and parse the output"""
        print("=" * 80)
        print("EXECUTING MINIZINC")
        print("=" * 80)
        print(f"Plan length k = {self.k}")
        print("=" * 80)

        cmd = ["minizinc", self.mzn_file, self.dzn_file, 
               "-D", f"k={self.k}", "--solver", "Chuffed"]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True)
            output = result.stdout

            # Print the original output
            print(output)
            print("=" * 80)

            # Parse the output
            self._parse_output(output)

            return True

        except subprocess.CalledProcessError as e:
            print(f"Error executing MiniZinc: {e}")
            print(f"stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            print("Error: minizinc command not found. Please install MiniZinc.")
            return False

    def _parse_dzn(self):
        """Parse the .dzn file to extract problem parameters"""
        with open(self.dzn_file, 'r') as f:
            content = f.read()

        # Extract N
        match = re.search(r'N\s*=\s*(\d+)', content)
        if match:
            self.N = int(match.group(1))

        # Extract h
        match = re.search(r'h\s*=\s*(\d+)', content)
        if match:
            self.h = int(match.group(1))

        # Extract adjacency matrix
        match = re.search(r'Adj\s*=\s*\[\|([^\]]+)\|\]', content, re.DOTALL)
        if match:
            matrix_str = match.group(1)
            rows = [line.strip()
                    for line in matrix_str.split('|') if line.strip()]
            self.adj_matrix = []
            for row in rows:
                # Remove comments
                row_clean = re.sub(r'%.*$', '', row).strip()
                if row_clean:
                    values = [int(x.strip())
                              for x in row_clean.split(',') if x.strip()]
                    self.adj_matrix.append(values)
            self.adj_matrix = np.array(self.adj_matrix)

        # Extract S_init
        match = re.search(r'S_init\s*=\s*\[([^\]]+)\]', content)
        if match:
            self.S_init = [int(x.strip()) for x in match.group(1).split(',')]

        # Extract T
        match = re.search(r'T\s*=\s*\[([^\]]+)\]', content)
        if match:
            self.T = [int(x.strip()) for x in match.group(1).split(',')]

        # Extract u
        match = re.search(r'u\s*=\s*(\d+)', content)
        if match:
            self.u = int(match.group(1))

    def _parse_output(self, output):
        """Parse MiniZinc output to extract states"""
        self._parse_dzn()  # First load problem parameters

        lines = output.strip().split('\n')

        # Parse initial state
        initial = TrucksState(0)

        for line in lines:
            if line.strip().startswith("Truck at node:") and "t=0" in lines[lines.index(line)-1]:
                # Initial state
                match = re.search(
                    r'Truck at node:\s*(\d+)\s*\(contents:\s*(\d+)\)', line)
                if match:
                    initial.truck_pos = int(match.group(1))
                    initial.truck_contents = int(match.group(2))

            if line.strip().startswith("Nodes:") and "t=0" in lines[lines.index(line)-2]:
                # Parse node objects from initial state
                match = re.search(r'\[(.*?)\]', line)
                if match:
                    node_data = match.group(1)
                    pairs = node_data.split(',')
                    for pair in pairs:
                        node_id, count = pair.split(':')
                        initial.node_objects[int(node_id.strip())] = int(
                            count.strip())

        self.states.append(initial)

        # Parse timesteps
        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for "Timestep X:"
            match = re.match(r'Timestep\s+(\d+):', line)
            if match:
                t = int(match.group(1))
                state = TrucksState(t)

                # Next lines contain the state info
                if i + 1 < len(lines):
                    # Load from, Loaded, Cross_E
                    load_line = lines[i + 1]
                    match = re.search(
                        r'Load from:\s*(\d+),\s*Loaded:\s*(\d+),\s*Cross_E:\s*(\d+)', load_line)
                    if match:
                        state.load_from = int(match.group(1))
                        state.loaded = int(match.group(2))
                        state.had_cross_e = int(match.group(3))

                if i + 2 < len(lines):
                    # Move to, Unloaded
                    move_line = lines[i + 2]
                    match = re.search(
                        r'Move to:\s*(\d+),\s*Unloaded:\s*(\d+)', move_line)
                    if match:
                        state.move_to = int(match.group(1))
                        state.unloaded = int(match.group(2))

                if i + 3 < len(lines):
                    # Truck position and contents
                    truck_line = lines[i + 3]
                    match = re.search(
                        r'Truck at node:\s*(\d+)\s*\(contents:\s*(\d+)\)', truck_line)
                    if match:
                        state.truck_pos = int(match.group(1))
                        state.truck_contents = int(match.group(2))

                if i + 4 < len(lines):
                    # Nodes
                    nodes_line = lines[i + 4]
                    match = re.search(r'\[(.*?)\]', nodes_line)
                    if match:
                        node_data = match.group(1)
                        pairs = node_data.split(',')
                        for pair in pairs:
                            node_id, count = pair.split(':')
                            state.node_objects[int(node_id.strip())] = int(
                                count.strip())

                self.states.append(state)

            i += 1

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
        """Determine node color based on its role (without truck position)"""
        # Target nodes - green
        if self.T[node_id - 1] == 1:
            return '#50C878'  # Green

        # Initial source nodes - light red
        if self.S_init[node_id - 1] > 0:
            return '#FFB6C1'  # Light pink/red

        # Normal nodes - gray
        return '#CCCCCC'  # Gray

    def _draw_state(self, state):
        """Draw the graph state at a specific timestep"""
        self.ax.clear()

        # Draw all edges in gray first
        nx.draw_networkx_edges(self.G, self.pos, ax=self.ax,
                               edge_color='#999999', width=2, alpha=0.6)

        # Draw cross_k edge in blue with arrow if we have a move
        if state.timestep > 0 and state.move_to:
            load_pos = state.load_from

            # The cross_k edge is from load_from to move_to
            if self.G.has_edge(load_pos, state.move_to):
                x1, y1 = self.pos[load_pos]
                x2, y2 = self.pos[state.move_to]

                arrow = FancyArrowPatch(
                    (x1, y1), (x2, y2),
                    arrowstyle='->,head_width=6,head_length=6',
                    color='#0066FF', linewidth=4,
                    alpha=0.9, zorder=3,
                    shrinkA=15, shrinkB=15  # Shrink from both ends to show arrow head
                )
                self.ax.add_patch(arrow)

        # Draw nodes with colors (without truck consideration)
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
            count = state.node_objects.get(node, 0)
            if count > 0:
                x, y = self.pos[node]
                self.ax.text(x, y - 0.17, f'OBJ: {count}',
                             ha='center', va='top', fontsize=9,
                             bbox=dict(boxstyle='round,pad=0.3',
                                       facecolor='yellow', alpha=0.8,
                                       edgecolor='black', linewidth=1))

        # Draw truck as a symbol above the node
        if state.truck_pos:
            x, y = self.pos[state.truck_pos]

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

            # Show load
            if state.truck_contents > 0:
                self.ax.text(x + 0.08, y + 0.2, f'[{state.truck_contents}]',
                             ha='left', va='center', fontsize=9,
                             color='red', weight='bold',
                             bbox=dict(boxstyle='round,pad=0.2',
                                       facecolor='white', alpha=0.9,
                                       edgecolor='red', linewidth=1.5))

        # Draw epsilon transition arrow if applicable
        if state.timestep > 0 and state.had_cross_e == 1:
            prev_state = self.states[state.timestep - 1]
            if prev_state.truck_pos != state.load_from:
                # Draw curved arrow from prev position to load_from
                x1, y1 = self.pos[prev_state.truck_pos]
                x2, y2 = self.pos[state.load_from]

                arrow = FancyArrowPatch(
                    (x1, y1), (x2, y2),
                    arrowstyle='->,head_width=6,head_length=6',
                    color='red', linewidth=3, linestyle='--',
                    connectionstyle='arc3,rad=0.3',
                    alpha=0.7, zorder=5,
                    shrinkA=15, shrinkB=15  # Shrink from both ends to show arrow head
                )
                self.ax.add_patch(arrow)

                # Add label
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                self.ax.text(mid_x, mid_y + 0.1, 'ε-transition',
                             ha='center', va='bottom', fontsize=9,
                             color='red', weight='bold',
                             bbox=dict(boxstyle='round,pad=0.3',
                                       facecolor='white', alpha=0.8))

        # Title with state information
        title = f'Timestep {state.timestep}'
        if state.timestep > 0:
            action_desc = []
            if state.had_cross_e:
                action_desc.append(f'ε-move to node {state.load_from}')
            if state.loaded > 0:
                action_desc.append(
                    f'Load {state.loaded} from node {state.load_from}')
            action_desc.append(f'Move to node {state.move_to}')
            if state.unloaded > 0:
                action_desc.append(f'Unload {state.unloaded}')

            title += '\n' + ' → '.join(action_desc)
        else:
            title += ' (Initial State)'

        self.ax.set_title(title, fontsize=12, weight='bold', pad=20)

        # Legend
        legend_elements = [
            plt.Line2D([0], [0], marker='s', color='w',
                       markerfacecolor='#4A90E2', markersize=10, label='Truck'),
            plt.Line2D([0], [0], marker='o', color='w',
                       markerfacecolor='#50C878', markersize=10, label='Target Node'),
            plt.Line2D([0], [0], marker='o', color='w',
                       markerfacecolor='#FFB6C1', markersize=10, label='Initial Source'),
            plt.Line2D([0], [0], marker='o', color='w',
                       markerfacecolor='#CCCCCC', markersize=10, label='Normal Node'),
            plt.Line2D([0], [0], color='#0066FF',
                       linewidth=3, label='Cross_K edge')
        ]
        self.ax.legend(handles=legend_elements, loc='upper left', fontsize=8)

        self.ax.axis('off')
        self.fig.canvas.draw_idle()

    def _next_step(self, event):
        """Go to next timestep"""
        if self.current_step < len(self.states) - 1:
            self.current_step += 1
            self._draw_state(self.states[self.current_step])

    def _prev_step(self, event):
        """Go to previous timestep"""
        if self.current_step > 0:
            self.current_step -= 1
            self._draw_state(self.states[self.current_step])

    def _first_step(self, event):
        """Go to first timestep"""
        self.current_step = 0
        self._draw_state(self.states[self.current_step])

    def _last_step(self, event):
        """Go to last timestep"""
        self.current_step = len(self.states) - 1
        self._draw_state(self.states[self.current_step])

    def _on_key(self, event):
        """Handle keyboard navigation"""
        if event.key == 'right':
            self._next_step(None)
        elif event.key == 'left':
            self._prev_step(None)
        elif event.key == 'home':
            self._first_step(None)
        elif event.key == 'end':
            self._last_step(None)

    def visualize(self):
        """Create interactive visualization"""
        if not self.states:
            print("No states to visualize. Run MiniZinc first.")
            return

        print("\n" + "=" * 80)
        print("INTERACTIVE VISUALIZATION")
        print("=" * 80)
        print("Controls:")
        print("  - Buttons: |<< | < | > | >>|  (First, Previous, Next, Last)")
        print("  - Keyboard: ← → (Previous/Next), Home/End (First/Last)")
        print("=" * 80 + "\n")

        self._build_graph()

        # Create figure and axes
        self.fig = plt.figure(figsize=(14, 10))
        self.ax = plt.subplot(111)

        # Make room for buttons
        plt.subplots_adjust(bottom=0.15)

        # Create buttons
        ax_first = plt.axes([0.2, 0.05, 0.1, 0.05])
        ax_prev = plt.axes([0.35, 0.05, 0.1, 0.05])
        ax_next = plt.axes([0.55, 0.05, 0.1, 0.05])
        ax_last = plt.axes([0.7, 0.05, 0.1, 0.05])

        self.btn_first = Button(ax_first, '|<<')
        self.btn_prev = Button(ax_prev, '<')
        self.btn_next = Button(ax_next, '>')
        self.btn_last = Button(ax_last, '>>|')

        self.btn_first.on_clicked(self._first_step)
        self.btn_prev.on_clicked(self._prev_step)
        self.btn_next.on_clicked(self._next_step)
        self.btn_last.on_clicked(self._last_step)

        # Connect keyboard events
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

        # Draw initial state
        self._draw_state(self.states[0])

        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Visualize Trucks Problem solution from MiniZinc'
    )
    parser.add_argument('-m', '--model', required=True, help='Path to .mzn file')
    parser.add_argument('-i','--instance', required=True, help='Path to .dzn file')
    parser.add_argument('-k','--k', type=int, required=True, help='Plan length (number of timesteps)')

    args = parser.parse_args()

    visualizer = TrucksVisualizer(args.model, args.instance, args.k)

    # Run MiniZinc
    if not visualizer.run_minizinc():
        sys.exit(1)

    # Visualize
    visualizer.visualize()


if __name__ == '__main__':
    main()