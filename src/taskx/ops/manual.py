import sys


def run_manual_mode(compiled_content: str, platform: str, model: str) -> None:
    print("\n=== TaskX Manual Mode ===")
    print("Please paste current system instructions (optional). End with a single line containing 'END':")
    system_input = []
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "END":
            break
        system_input.append(line)
    
    print("\nPlease paste current project instructions (optional). End with a single line containing 'END':")
    project_input = []
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "END":
            break
        project_input.append(line)
        
    print("\n--- MERGED OUTPUT ---")
    if system_input:
        print("### Existing System Instructions (pasted)")
        print("".join(system_input))
    
    if project_input:
        print("\n### Existing Project Instructions (pasted)")
        print("".join(project_input))
        
    print("\n### TaskX Addendum")
    print(compiled_content)
    print("--- END MERGED OUTPUT ---")
