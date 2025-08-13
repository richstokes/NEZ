# Project Overview
We are writing a NES emulator in python.


# Workflow
1. Run the emulator with: `./run_and_log.sh` -- it will start the emulator and log output to `log.log`. I will stop the emulator after letting it run for a while.
2. Ask me how well it worked / if I saw any issues or errors.
3. grep or head or tail the log.log file for relevant information. Use this to help debug and fix the emulator.


# Important considerations
- Check if a similar method exists before adding a new one. We don't want duplicates or cluttered code
- If you're unsure, review the #codebase to understand the logic/flow completely before working on a solution
- If you need to add debug logging, use the `debug_print` function from utils.py to log messages. This will help in tracking down issues without cluttering the output.
- Don't create new files unless absolutely necessary. Use existing files and methods to keep the codebase clean and maintainable.
- Don't create documentation


# References
Use https://github.com/ObaraEmmanuel/NES as a reference for how the code should work. 

https://github.com/bokuweb/rustynes/tree/master/src also has good info.
