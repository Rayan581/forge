import os
import sys
import subprocess
import time

def main():
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(tools_dir)
    report_dir = os.path.join(root_dir, "docs", "reports", "mid_report", "latex")
    tectonic_exe = os.path.join(tools_dir, "bin", "tectonic.exe")

    if not os.path.exists(tectonic_exe):
        print(f"[ERROR] Tectonic compiler not found at: {tectonic_exe}")
        sys.exit(1)

    if not os.path.exists(report_dir):
        print(f"[ERROR] Report directory not found at: {report_dir}")
        sys.exit(1)

    print("=" * 60)
    print("Project FORGE — Local LaTeX Compilation Engine")
    print("=" * 60)
    print(f"Target Directory: {report_dir}")
    print(f"Compiler:         {tectonic_exe}")
    print("Building main.tex into main.pdf...")
    start_time = time.time()

    cmd = [tectonic_exe, "main.tex"]
    result = subprocess.run(cmd, cwd=report_dir)

    elapsed = time.time() - start_time

    built_pdf = os.path.join(report_dir, "main.pdf")
    dest_filename = "FORGE__Personalized_Procedural_Content_Generation_via_Reinforcement_Learning.pdf"
    dest_pdf = os.path.join(root_dir, "docs", "reports", "mid_report", dest_filename)

    if result.returncode == 0 and os.path.exists(built_pdf):
        import shutil
        shutil.copy2(built_pdf, dest_pdf)
        size_mb = os.path.getsize(dest_pdf) / (1024 * 1024)
        print("=" * 60)
        print(f"[SUCCESS] Compilation finished in {elapsed:.2f} seconds!")
        print(f"Output PDF: {dest_pdf}")
        print(f"File Size:  {size_mb:.2f} MB")
        print("=" * 60)
    else:
        print("=" * 60)
        print(f"[FAILURE] Compilation failed with exit code {result.returncode}")
        print("=" * 60)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
