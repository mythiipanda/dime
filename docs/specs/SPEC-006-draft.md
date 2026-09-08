# SPEC-006: Draft combine explorer

Problem: draft analysts blend measurements with shooting. Data lives in
combine endpoints nobody browses.

Change: `get_combine` joins anthro plus spot shooting. Dataset endpoint
serves it by draft year. Explore tab renders the table.

Surface: year input plus table. No model yet. Star probability waits for
a trained classifier with proper validation.

Verify: dataset returns rows with height and wingspan columns. Browser
shows the table.
