#!/usr/bin/env python3
import sys
import os
import re
from functions import verilogFuncs

def main():
    # Usage:
    #   python3 thesis.py <H|V> <Verilog_File> [Top_Module_Name] [debug] [--gate <gate_instance>]
    if len(sys.argv) < 3:
        print("Usage: python3 thesis.py <H|V> <Verilog_File> [Top_Module_Name] [debug] [--gate <gate_instance>]")
        sys.exit(1)

    mode         = sys.argv[1]
    verilog_file = sys.argv[2]

    # Optional top‐module
    top_module = ""
    idx = 3
    if idx < len(sys.argv) and sys.argv[idx] not in ("debug", "--gate"):
        top_module = sys.argv[idx]
        idx += 1

    debug         = False
    gate_instance = None

    # Process the rest of the flags
    while idx < len(sys.argv):
        arg = sys.argv[idx]
        if arg.lower() == "debug":
            debug = True
        elif arg == "--gate":
            if idx + 1 < len(sys.argv):
                gate_instance = sys.argv[idx + 1]
                idx += 1
            else:
                print("Error: --gate flag requires a gate instance name")
                sys.exit(1)
        else:
            print("Unrecognized argument:", arg)
        idx += 1

    if mode not in ('H', 'V'):
        print("Mode must be 'H' (hierarchical) or 'V' (flat)")
        sys.exit(1)

    # Parse the Verilog file
    modules = verilogFuncs.parse_hierarchical_verilog(verilog_file)

    # Auto-detect top if needed
    if not top_module:
        top_module = verilogFuncs.find_top_module(modules)
        if not top_module:
            print("Top module not found in parsed file.")
            sys.exit(1)

    # If a specific gate is requested:
    if gate_instance:
        # Find the instance in the top module
        inst = next((i for i in modules[top_module]['instances']
                     if i['instance_name'] == gate_instance),
                    None)
        if inst is None:
            print(f"Instance '{gate_instance}' not found in top module '{top_module}'.")
            sys.exit(1)

        gate_type = inst['module']
        
        # Map hierarchical modules to primitives if needed
        if gate_type == "full_adder":
            gate_type = "FA"  # Map full_adder to FA primitive
        elif gate_type == "half_adder":
            gate_type = "HA"  # Map half_adder to HA primitive
            
        if gate_type not in verilogFuncs.primitive_ports:
            print(f"Gate type '{gate_type}' is not a supported primitive.")
            sys.exit(1)

        # Ask if they want to simulate gate locally
        local_only = input("Simulate gate locally only? (y/n): ").strip().lower()
        
        if local_only.startswith("n"):
            # Use values from full circuit simulation
            input_vals = verilogFuncs.get_input_values(modules[top_module]['inputs'])
            signal_values = {}
            verilogFuncs.simulate_module(modules, top_module, input_vals, signal_values, debug=debug)
            
            # Get the signal values for this instance
            in_vals = {}
            for conn in inst["connections"]:
                role = conn.get("port")
                signal = conn["signal"]
                in_vals[role] = signal_values.get(f"{top_module}_{signal}", 0)
                
        else:
            # Local gate testing: directly ask for gate inputs
            inputs = verilogFuncs.primitive_ports[gate_type]['inputs']
            load = input("Load gate inputs from .txt? (y/n): ").strip().lower()
            if load.startswith("y"):
                fn = input("file name: ").strip()
                bits = re.sub(r"[,\s]", "", open(fn).read())
                if len(bits) != len(inputs):
                    raise ValueError(f"bit-count mismatch (expected {len(inputs)}, got {len(bits)})")
                in_vals = {p: int(bits[i]) for i, p in enumerate(inputs)}
                print("Loaded from file.")
            else:
                in_vals = {}
                print(f"Enter each input (0/1) for {gate_instance}")
                for p in inputs:
                    v = ""
                    while v not in ("0", "1"):
                        v = input(f"  {p} (0/1)? ").strip()
                    in_vals[p] = int(v)

        # Run the primitive simulation with the values
        out_vals = verilogFuncs.primitive_simulators[gate_type](in_vals)

        # Build port_info for DOT visualization  
        port_info = {}  # simple basic: create signal -> value mapping for DOT visualization
        for role in in_vals:
            port_info[role] = (f"input_{role.lower()}", in_vals[role])
        for role in out_vals:
            port_info[role] = (f"output_{role.lower()}", out_vals[role])

        print(f"Input values: {in_vals}")
        print(f"Output values: {out_vals}")

        # Generate DOT and PDF with proper visual representation
        dot = f"{gate_instance}_{gate_type}.dot"
        pdf = f"{gate_instance}_{gate_type}.pdf"
        
        # Use specialized layout for different gate types
        if gate_type == "FA":
            verilogFuncs.generate_FA_dot(dot, gate_instance, port_info)
        elif gate_type == "HA":
            verilogFuncs.generate_HA_dot(dot, gate_instance, port_info)
        else:
            verilogFuncs.generate_primitive_dot(dot, gate_type, gate_instance, port_info)
            
        print(f"\nConverting {dot} to PDF…")
        if os.system(f"dot -Tpdf {dot} -o {pdf}") == 0:
            print(f"✅ Generated '{pdf}'.")
        else:
            print("❌ dot → PDF failed; check Graphviz installation.")
        return

    else:
        # No --gate: normal full‐design simulation
        input_vals = verilogFuncs.get_input_values(modules[top_module]['inputs'])
        signal_values = {}
        verilogFuncs.simulate_module(modules,
                                     top_module,
                                     input_vals,
                                     signal_values,
                                     debug=debug)
        dot_file = 'hierarchy.dot'
        verilogFuncs.generate_layered_dot(modules,
                                         top_module,
                                         dot_file,
                                         signal_values)
        print(f"\nSimulation complete. DOT file generated as '{dot_file}'.")
        pdf_file = 'hierarchy.pdf'
        print(f"\nConverting {dot_file} to PDF…")
        if os.system(f"dot -Tpdf {dot_file} -o {pdf_file}") == 0:
            print(f"✅ Generated '{pdf_file}'.")
        else:
            print("❌ dot → PDF failed; check Graphviz installation.")

if __name__ == "__main__":
    main()
