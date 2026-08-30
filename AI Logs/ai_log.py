import json
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path
from datetime import date
from openpyxl import load_workbook


# ============================================================
# SETTINGS
# ============================================================

EXCEL_FILE = "AI logs.xlsx"

# Leave as None to use the active/first worksheet.
# Or change to something like:
# SHEET_NAME = "AI Usage Log"
SHEET_NAME = None


HEADERS = [
    "Log ID",
    "Date",
    "Team Member",
    "Project Phase",
    "Task / Activity",
    "AI Tool / Model",
    "Prompt / Query",
    "Purpose of AI Use",
    "AI Output / Summary",
    "How Output Was Used",
    "Human Verification / Review",
    "Changes Made After Review",
    "Final Use in Project",
    "File / Section Affected",
    "AI Contribution Type",
    "Source Verification",
    "Accepted / Rejected",
    "Notes"
]

PROJECT_PHASES = [
    "Proposal",
    "Design",
    "Implementation",
    "Testing",
    "Documentation"
]

DECISION_OPTIONS = [
    "Accepted",
    "Modified",
    "Rejected"
]

CONTRIBUTION_TYPES = [
    "Brainstorming",
    "Writing",
    "Coding",
    "Debugging",
    "Research",
    "Analysis",
    "Editing"
]


# ============================================================
# GET JSON FROM USER / CLIPBOARD
# ============================================================

def get_json_from_user():
    root = tk.Tk()
    root.withdraw()

    # Try checking clipboard automatically
    clipboard_data = None
    try:
        raw_clip = root.clipboard_get().strip()
        if raw_clip.startswith("{") and raw_clip.endswith("}"):
            try:
                clipboard_data = json.loads(raw_clip)
            except Exception:
                clipboard_data = None
    except Exception:
        clipboard_data = None

    if clipboard_data and isinstance(clipboard_data, dict):
        response = messagebox.askyesno(
            "AI Usage Log",
            "Valid JSON detected on clipboard!\n\n"
            "Would you like to use the clipboard content?"
        )
        if response:
            root.destroy()
            return clipboard_data

    # Check entry.json file in script directory as fallback
    entry_file = Path(__file__).resolve().parent / "entry.json"
    if entry_file.exists():
        try:
            with open(entry_file, "r", encoding="utf-8") as f:
                file_data = json.load(f)
            if isinstance(file_data, dict):
                response = messagebox.askyesno(
                    "AI Usage Log",
                    f"Found entry data in {entry_file.name}!\n\n"
                    "Would you like to use this entry?"
                )
                if response:
                    root.destroy()
                    return file_data
        except Exception:
            pass

    messagebox.showinfo(
        "AI Usage Log",
        "Copy the JSON produced by the AI.\n\n"
        "The next window will ask you to paste it."
    )

    json_text = simpledialog.askstring(
        "Paste AI JSON",
        "Paste the AI-generated JSON here:"
    )

    root.destroy()

    if not json_text:
        raise ValueError("No JSON was provided.")

    return json.loads(json_text.strip())


# ============================================================
# OPEN EXCEL FILE
# ============================================================

def get_excel_path():
    # Look in the script directory first, then current working directory
    script_dir = Path(__file__).resolve().parent
    path_in_script_dir = script_dir / EXCEL_FILE
    if path_in_script_dir.exists():
        return path_in_script_dir

    path_in_cwd = Path(EXCEL_FILE)
    if path_in_cwd.exists():
        return path_in_cwd

    raise FileNotFoundError(
        f"Could not find '{EXCEL_FILE}'.\n\n"
        f"Looked in:\n- {path_in_script_dir}\n- {path_in_cwd.resolve()}\n\n"
        "Make sure the Python script and Excel file are in the same folder."
    )


def open_workbook():
    excel_path = get_excel_path()
    workbook = load_workbook(excel_path)

    if SHEET_NAME:
        if SHEET_NAME not in workbook.sheetnames:
            raise ValueError(
                f"Worksheet '{SHEET_NAME}' was not found.\n\n"
                f"Available sheets: {workbook.sheetnames}"
            )
        worksheet = workbook[SHEET_NAME]
    else:
        worksheet = workbook.active

    return workbook, worksheet, excel_path


# ============================================================
# FIND EXCEL COLUMNS
# ============================================================

def get_column_mapping(worksheet):
    mapping = {}

    for cell in worksheet[1]:
        if cell.value is not None:
            header = str(cell.value).strip()
            mapping[header] = cell.column

    missing = [
        header
        for header in HEADERS
        if header not in mapping
    ]

    if missing:
        raise ValueError(
            "These required columns are missing from the Excel sheet:\n\n"
            + "\n".join(missing)
        )

    return mapping


# ============================================================
# GENERATE LOG ID
# ============================================================

def generate_log_id(worksheet, column_number):
    highest_number = 0

    for row in range(2, worksheet.max_row + 1):
        value = worksheet.cell(row=row, column=column_number).value
        if value is None:
            continue

        text = str(value).strip()
        if text.startswith("AI-"):
            try:
                number = int(text[3:])
                highest_number = max(highest_number, number)
            except ValueError:
                pass

    return f"AI-{highest_number + 1:03d}"


# ============================================================
# REVIEW & COMPLETE FORM GUI
# ============================================================

def review_and_complete_form(initial_data, auto_log_id):
    """
    Displays a GUI form allowing the user to review and fill in
    missing fields (Team Member, Accepted / Rejected, etc.) before saving.
    """
    root = tk.Tk()
    root.title(f"Review AI Usage Log Entry — {auto_log_id}")
    root.geometry("760x780")
    root.minsize(600, 500)

    # Center window
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(0, int((screen_width - 760) / 2))
    y = max(0, int((screen_height - 780) / 2))
    root.geometry(f"760x780+{x}+{y}")

    result_data = {}
    is_cancelled = {"value": True}

    # Header title banner
    top_frame = ttk.Frame(root, padding=(15, 10))
    top_frame.pack(fill=tk.X)
    title_lbl = ttk.Label(
        top_frame,
        text="Review & Complete Log Entry",
        font=("Segoe UI", 13, "bold")
    )
    title_lbl.pack(anchor="w")
    sub_lbl = ttk.Label(
        top_frame,
        text="Please fill in missing fields (e.g. Team Member, Accepted/Rejected) and make any needed edits.",
        font=("Segoe UI", 9)
    )
    sub_lbl.pack(anchor="w", pady=(2, 0))

    # Canvas with scrollbar for content
    container = ttk.Frame(root)
    container.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding=(5, 5))

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    def on_canvas_configure(event):
        canvas.itemconfig(canvas_frame, width=event.width)

    canvas.bind("<Configure>", on_canvas_configure)
    canvas.configure(yscrollcommand=scrollbar.set)

    # Mousewheel scrolling
    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", on_mousewheel)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Multi-line fields list
    multiline_headers = {
        "Prompt / Query",
        "Purpose of AI Use",
        "AI Output / Summary",
        "How Output Was Used",
        "Human Verification / Review",
        "Changes Made After Review",
        "Final Use in Project",
        "Notes"
    }

    widget_map = {}

    for row_idx, header in enumerate(HEADERS):
        row_frame = ttk.Frame(scrollable_frame, padding=(0, 4))
        row_frame.pack(fill=tk.X, expand=True)

        lbl = ttk.Label(
            row_frame,
            text=header + ( " *" if header in ["Team Member", "Accepted / Rejected"] else "" ),
            font=("Segoe UI", 9, "bold" if header in ["Team Member", "Accepted / Rejected"] else "normal"),
            width=26,
            anchor="w"
        )
        lbl.pack(side=tk.LEFT, anchor="n", pady=2)

        val = initial_data.get(header, "")
        if header == "Log ID" and not val:
            val = auto_log_id
        elif header == "Date" and not val:
            val = date.today().isoformat()

        if header == "Project Phase":
            cb = ttk.Combobox(row_frame, values=PROJECT_PHASES, state="normal")
            cb.set(val if val else "Proposal")
            cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            widget_map[header] = cb

        elif header == "Accepted / Rejected":
            cb = ttk.Combobox(row_frame, values=DECISION_OPTIONS, state="normal")
            cb.set(val if val else "Accepted")
            cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            widget_map[header] = cb

        elif header == "AI Contribution Type":
            cb = ttk.Combobox(row_frame, values=CONTRIBUTION_TYPES, state="normal")
            cb.set(str(val) if val else "")
            cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            widget_map[header] = cb

        elif header in multiline_headers:
            txt = tk.Text(row_frame, height=3, wrap="word", font=("Segoe UI", 9))
            txt.insert("1.0", str(val) if val is not None else "")
            txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
            widget_map[header] = txt

        else:
            entry = ttk.Entry(row_frame, font=("Segoe UI", 9))
            entry.insert(0, str(val) if val is not None else "")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            widget_map[header] = entry

            # Auto-focus on Team Member if empty
            if header == "Team Member" and not val:
                entry.focus_set()

    # Buttons frame
    btn_frame = ttk.Frame(root, padding=(15, 10))
    btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

    def on_save():
        # Validate Team Member
        team_member = widget_map["Team Member"].get().strip()
        if not team_member:
            if not messagebox.askyesno(
                "Missing Team Member",
                "Team Member field is currently blank.\n\nDo you want to save anyway?"
            ):
                widget_map["Team Member"].focus_set()
                return

        for h in HEADERS:
            w = widget_map[h]
            if isinstance(w, tk.Text):
                result_data[h] = w.get("1.0", "end-1c").strip()
            elif isinstance(w, ttk.Combobox) or isinstance(w, ttk.Entry):
                result_data[h] = w.get().strip()
            else:
                result_data[h] = ""

        is_cancelled["value"] = False
        canvas.unbind_all("<MouseWheel>")
        root.destroy()

    def on_cancel():
        canvas.unbind_all("<MouseWheel>")
        root.destroy()

    cancel_btn = ttk.Button(btn_frame, text="Cancel", command=on_cancel)
    cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))

    save_btn = ttk.Button(btn_frame, text="Save to Excel", command=on_save)
    save_btn.pack(side=tk.RIGHT, padx=5)

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    if is_cancelled["value"]:
        raise KeyboardInterrupt("Operation cancelled by user.")

    return result_data


# ============================================================
# ADD ENTRY TO WORKSHEET
# ============================================================

def add_entry(data, worksheet, column_mapping):
    next_row = worksheet.max_row + 1

    for header in HEADERS:
        column = column_mapping[header]
        value = data.get(header, "")
        worksheet.cell(
            row=next_row,
            column=column,
            value=value
        )

    return next_row, data.get("Log ID", "")


# ============================================================
# MAIN
# ============================================================

def main():
    try:
        print("Reading AI-generated JSON...")
        data = get_json_from_user()

        print("Opening Excel workbook...")
        workbook, worksheet, excel_path = open_workbook()

        print("Checking Excel columns...")
        column_mapping = get_column_mapping(worksheet)

        # Generate automatic Log ID
        log_id_col = column_mapping["Log ID"]
        auto_log_id = generate_log_id(worksheet, log_id_col)

        print("Opening Review & Completion form...")
        reviewed_data = review_and_complete_form(data, auto_log_id)

        print("Adding AI usage entry...")
        row_number, log_id = add_entry(
            reviewed_data,
            worksheet,
            column_mapping
        )

        # ----------------------------------------------------
        # Save Excel file
        # ----------------------------------------------------
        workbook.save(excel_path)

        print()
        print("SUCCESS")
        print("--------------------------------")
        print(f"Log ID      : {log_id}")
        print(f"Date        : {reviewed_data.get('Date', date.today().isoformat())}")
        print(f"Team Member : {reviewed_data.get('Team Member', 'N/A')}")
        print(f"Status      : {reviewed_data.get('Accepted / Rejected', 'N/A')}")
        print(f"Row         : {row_number}")
        print(f"File        : {excel_path.name}")
        print("--------------------------------")

        # Show success popup
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "AI Usage Log",
            f"Successfully added entry {log_id} to row {row_number}!\n\n"
            f"Team Member: {reviewed_data.get('Team Member', 'N/A')}\n"
            f"Decision: {reviewed_data.get('Accepted / Rejected', 'N/A')}\n"
            f"File: {excel_path.name}"
        )
        root.destroy()

    except KeyboardInterrupt:
        print("\nLog entry was cancelled.")

    except json.JSONDecodeError:
        print("ERROR: The AI output was not valid JSON.")
        print("Make sure you copied the complete JSON response.")

    except Exception as error:
        print(f"ERROR: {error}")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "AI Usage Log Error",
                str(error)
            )
            root.destroy()
        except Exception:
            pass


# ============================================================
# RUN PROGRAM
# ============================================================

if __name__ == "__main__":
    main()