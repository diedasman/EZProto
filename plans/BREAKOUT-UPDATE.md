# BREAKOUT BOARD GENERATOR UPDATE

This document will outline a plan to update the breakout board generation tool.  
The tool works in practice with basic functionality, but requires quality of life improvements.  
The goal of this update is to improve usability, readability of generated layouts, and overall consistency with existing tooling in the application.

---

## Core Generation

- Currently generated breakouts have traces that overlap and do not use 45 degree routing angles.  
- Update the core generation with basic design rules;  
    - Ensure traces do not intersect or overlap by introducing simple collision avoidance during routing  
    - Enforce 45° and 90° trace angles for cleaner and more manufacturable layouts  
    - Maintain consistent spacing between traces and pads based on standard PCB clearance practices  
    - Introduce a basic routing order (e.g., prioritize shortest path first or directional routing per side)  
    - Ensure symmetry where applicable, especially for footprints with evenly distributed pins  
    - Validate generated output to prevent invalid geometries before exporting  

---

## UI Changes

- Move footprint file directory input and label to the top of the list.  
    - Set the input field width to auto  
    - Ensure long paths are still readable (truncate visually if needed, but preserve full value internally)  

- Move Board Name input and label to the bottom.  
    - Place Generate button to the right of the input field  
    - Align both elements for a clean horizontal grouping  

- Pack Items into tighter grid  
    - Reduce unnecessary spacing between controls while maintaining readability  
    - Ensure alignment consistency across all rows  
    - Use the following layout:

    ```
    Board Width   [              ]   Board Height    [           ]
    Header        [              ]   Side margin     [           ] 
    ```

    - Maintain consistent input field sizes where appropriate  
    - Ensure layout scales reasonably with window resizing  

---

## Features to add

- Add footprint preview inside right panel at the top  
    - Display as much information as possible about the footprint; width, height, connections, etc.  
    - Render a simplified visual representation of pads and outline  
    - Ensure preview updates dynamically when a new footprint is selected  
    - Provide basic zoom or fit-to-view capability if space allows  

- Trace width, add predefined size buttons and custom value specification  
    - Location: below pitch  
    - Provide commonly used trace widths as quick-select buttons  
    - Allow manual input for custom values with validation  
    - Ensure selected value is clearly indicated in the UI  

- Rounded corners; use same method used for protoboard generation and UI widgets  
    - Apply consistent corner radius logic across both PCB generation and UI components  
    - Ensure rounded edges are correctly reflected in exported board outlines  
    - Maintain compatibility with manufacturing constraints  