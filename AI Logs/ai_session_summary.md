I am maintaining an AI Usage Log for my FYP project.

Review the ENTIRE conversation/session above and generate ONE AI-usage-log entry based only on what actually happened in this session.

Do NOT invent activities, decisions, sources, code usage, or project outcomes that are not supported by the conversation.

My Excel columns are:

1. Log ID
2. Date
3. Team Member
4. Project Phase
5. Task / Activity
6. AI Tool / Model
7. Prompt / Query
8. Purpose of AI Use
9. AI Output / Summary
10. How Output Was Used
11. Human Verification / Review
12. Changes Made After Review
13. Final Use in Project
14. File / Section Affected
15. AI Contribution Type
16. Source Verification
17. Accepted / Rejected
18. Notes

Return ONLY valid JSON. Do not use Markdown, code fences, explanations, or extra text.

Use this exact JSON structure:

{
  "Log ID": "",
  "Date": "",
  "Team Member": "",
  "Project Phase": "",
  "Task / Activity": "",
  "AI Tool / Model": "",
  "Prompt / Query": "",
  "Purpose of AI Use": "",
  "AI Output / Summary": "",
  "How Output Was Used": "",
  "Human Verification / Review": "",
  "Changes Made After Review": "",
  "Final Use in Project": "",
  "File / Section Affected": "",
  "AI Contribution Type": "",
  "Source Verification": "",
  "Accepted / Rejected": "",
  "Notes": ""
}

Rules:

- "Log ID": leave blank. The Excel script will generate it automatically.
- "Date": leave blank. I will enter the date myself.
- "Team Member": leave blank. I will enter the responsible team member myself.
- "Accepted / Rejected": leave blank. I will decide this myself after reviewing the AI output.
- "Final Use in Project": leave blank unless the conversation clearly shows that the output has already been incorporated into the project. Do not assume future use.
- For every other field, infer the value from the actual conversation.
- If a field cannot be determined from the conversation, write "Not determined from session" rather than inventing information.
- "Prompt / Query" should summarize the important requests I made during this session, not reproduce the entire conversation.
- "AI Output / Summary" should summarize the useful AI assistance actually provided.
- "How Output Was Used" should describe what happened in the session. If there is no evidence that I used the output yet, write "Reviewed as guidance; final use not yet determined."
- "Human Verification / Review" should state what verification was actually performed in the conversation. If none occurred, write "Not verified during this session."
- "Changes Made After Review" should only describe changes that are actually visible in the conversation.
- "Source Verification" should only list sources/papers/files that were actually checked or discussed. If no external/source verification occurred, write "No external source verification performed."
- "Project Phase" must be inferred as exactly one of:
  "Proposal", "Design", "Implementation", "Testing", "Documentation"
- "AI Contribution Type" must be one or more suitable options chosen from this exact list (comma-separated if multiple):
  "Brainstorming", "Writing", "Coding", "Debugging", "Research", "Analysis", "Editing"
- Keep the values concise enough to fit comfortably in an Excel cell.
- The entry must describe the actual AI assistance, not exaggerate its importance.