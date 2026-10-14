# Training Disclosure for MultiLabelZ
This Training Disclosure, which may be more specifically titled above here (and in this document possibly referred to as "this disclosure"), is based on **Training Disclosure version 1.1.4** at https://github.com/Hierosoft/training-disclosure by Jake Gustafson. Jake Gustafson is probably *not* an author of the project unless listed as a project author, nor necessarily the disclosure editor(s) of this copy of the disclosure unless this copy is the original which among other places I, Jake Gustafson, state IANAL. The original disclosure is released under the [CC0](https://creativecommons.org/public-domain/cc0/) license, but regarding any text that differs from the original:

This disclosure also functions as a claim of copyright to the scope described in the paragraph below since potentially in some jurisdictions output not of direct human origin, by certain means of generation at least, may not be copyrightable (again, IANAL):

Various author(s) may make claims of authorship to content in the project not mentioned in this disclosure, which this disclosure by way of omission unless stated elsewhere implies is of direct human origin unless stated elsewhere. Such statements elsewhere are present and complete if applicable to the best of the disclosure editor(s) ability. Additionally, the project author(s) hereby claim copyright and claim direct human origin to any and all content in the subsections of this disclosure itself, where scope is defined to the best of the ability of the disclosure editor(s), including the subsection names themselves, unless where stated, and unless implied such as by context, being copyrighted or trademarked elsewhere, or other means of statement or implication according to law in applicable jurisdiction(s).

Disclosure editor(s): Hierosoft LLC

Project author: Hierosoft LLC

This disclosure is a voluntary of how and where content in or used by this project was produced by LLM(s) or any tools that are "trained" in any way.

The main section of this disclosure lists such tools. For each, the version, install location, and a scope of their training sources in a way that is specific as possible.

Subsections of this disclosure contain prompts used to generate content, in a way that is complete to the best ability of the disclosure editor(s).

tool(s) used:
- Grok

Scope of use: code described in subsections--typically modified by hand to improve logic, variable naming, integration, etc, but in this commit, unmodified except adding "Print multiple labels on Zebra: adjust layout, and query a set of lines from a CSV file by a specific PO #!" to README.md and merging generated lines into default GitHub .gitignore and adding relevant comments:
```diff
+# OS-specific
+*.swp
+*~
+.DS_Store
+Thumbs.db
+
+# project-specific
+settings.json
```

## *.py, README.md, .gitignore
- https://grok.com/c/0e2a246a-04c7-49f9-8481-d554546c0dd1?rid=e8ab7792-5a91-4bf8-bfa2-faaa699fa4ef

I want a way to print labels to a 4x6 zebra label. It has to support bar codes. I prefer to be able to print from a spreadsheet and get asked for a PO number so filter which entries are printed, but we can do the filtering and print the template from cli to print from csv if the label program has a cli but not a csv query option. So far I am looking at QZ Tray, Label Nation, and ZPLab. Look for a free program, prefrably open source. I dont' want a web service, because I need to print from a spreadsheet in a fixed csv file location or at least a google sheet. I don't want to have to choose/upload the sheet every time. BarTender was working fine querying a csv but we don't want a service and the activation for the old disc version of BarTender that doesn't require a service plan is being deprecated at the end of 2027.
- [sic]

Implement a GUI with tkinter. Subclass Frame but not Tk. The fixed CSV location is ~/Downloads/{selected_filename} but look for files with (1) etc before the .csv and use the highest number if present. Use expanduser. Show the file in an entry, but put a refresh button by it to find the latest in case one was saved after the program loaded. If no such files are present then inform the user they must save the Batches table as CSV from the {os.path.splitext(given_filename)[0]} Google Doc or elsewhere so it is in the Downloads folder. Make a settings notebook tab that has the CSV filename. Add a print button that is "Print to" and disabled if no printer is selected. Show printer name in drop-down of printers directly to right of the button and enable button if set. Add a refresh button to the right of the drop-down to refresh printer list. Handle a print exception (off/invalid/disconnected). Save selected printer and input filename  settings both to os.environ['LOCALAPPDATA'] (or ~/.config if that is not in environ) /multilabelz/settings.json. If not Windows, assume Linux and use an a different (OS-appropriate) means of populating printer list. Require entering a PO number before printing, and copy the CSV to a filtered CSV (with rows matching the entered PO in the 'PO #' column; but keep the title row. Assume the first row is a title row on load, and:
```
if titleRow is None:
    titleRow = row
    continue
rowD = OrderedDict()
for idx in row:
    rowD[titleRow[idx]] = row[idx]
#logic for non-title row here (only write to dated file if matches PO, etc)
```
.) with today's date in parenthesis appended to the filename and place it in ~/Documents. Append (1) and successive numbers  if file already exists (if unnumbered exists, iterate number until proposed name does not exist). Initially save to a .tmp file until file is complete, then rename it. We need to print the following columns: | P/N | Notice | PO # | Batch # | Qty | Date Code | Ship Date . Do not put a caption for compliance notice--if the field is blank, simply print nothing. If it is not blank, simply print the value. I attached an example of where to place the fields. The top left sender and address should be fields in our program and saved to the settings file. on print/exit. Ship date should be able to be set, but should not be saved. It should always be blank. There should a hint ttk.Label saying to leave date blank to use Ship Date in spreadsheet (or none if blank in sheet). Add a readonly label at the bottom of the window that shows the current pending operation that is change to a success/fail message. Show Add a 3rd tab in the notebook that is the "Log" and append P/N and Quantity as a new line there each time a row from the csv it printed (show success /fail at the end of the line). Add a Copy button that copies the whole log to the clipboard, as well as a save button that asks , but note that it is portrait (The dark gray area of the screenshot is just overflow I included so you can see the field names, but any part starting with FIELD or Field should be replaced with the value from the spreadsheet). where to save the log (start in ~/Documents and set filter to txt, and make default filename MultiLabelZ-{date_str}.log in YYYY-MM-DD format). Add a thread-safe setStatus method that uses self.root.after_idle to set the status. Do a similar thread-safe method for logLine to add a new line to the log box.

The settings dict should be an OrderedDict. Make the primary tab with the print buttons called "Layout" which has the layout coordinates and shows them as draggable squares (gray outline, with field name inside). Save on print/exit or leaving the tab. Make a new section in the json for the coordinates and the field list. Make the list of fields names and every number configurable via json but make the default values what we have so far. We can deal with additional GUI features later (For now just let user move the fields around by dragging and allow selecting one at a time). Make the outline of the selected one black. Make the background of the canvas white. Add a "Snap: " tk.Label followed by X and Y buttons that snap the selected item to the divisor on the respective axis. After the buttons put a " to: 1/" then the divisor Entry, then '" = {decimal}"'. Update the label to the decimal value rounded to 4 decimal places. Use Decimal to avoid float rounding errors. Default to 8 (1/8 inch). Make a getDivisor method that gets the grid_divisor value from json, converts it to Decimal and returns tuple of Decimal, None (or returns (None, str) with error tuple if fails). If has error, show the error and use the default, and save the default to the settings OrderedDict. Always load settings with object pairs hook OrderedDict. Always save with indent=2. Make a way to choose landscape or portrait, portrait by default. In settings there should also be a label size in inches, w = 4, h = 6 by default. Save as str, load as Decimal. Make some way to configure the font size of each label, also in json, with defaults matching my screenshot as accurately as possible, assuming white part of label is 4x6 inches. Add any other font feature available in zpl, such as font or bold. Try to represent the font, face, and size as well as possible in the canvas. Make the canvas a good resolution for doing this right, but no more than half the screen height. Divide the font size for display purposes (if canvas is 600 pixels high, a .5 inch font should be 50 pixels, for instance, since the canvas print size is 6 inches [.5/6 * 600 = 50]). Determine the canvas size on startup based on the entire screen's height. In the JSON, if caption is null or "", show no caption, only the value; so Caption should have a null label by default to be the most specific. For each label, have a barcode key in json. If key is set, value is barcode type. If not present, do not generate a barcode for the value. In the Canvas, just show a solid gray box where the bar code would be. Have a checkbox that turns the barcode on or off for the selected item (disabled if nothing is selected). Ensure the box is updated whenever an item is selected. Each item should somehow store (subclass if necessary; or monkeypatch the object) the key in the settings['canvas_items'] OrderedDict so we know which item it edits.

Make a pyproject.toml and dependencies.txt. Project location is https://github.com/Hierosoft/multilabelz. Email is 7557867+Poikilos@users.noreply.github.com. Author is Jake Gustafson. License is GPL v3.0. Make  getDecimal and setDecimal static methods that are generic and make getDecimal replace getDivisor. Make similar settings for individual objects: getCanvasDecimal(self, itemKey, valueKey) and corresponding setCanvasDecimal. Add any other arg(s) necessary to access the correct item value (such as coordKey which could be x, y, width, height, or whatever, probably a separate function. Just make a getCanvasCoords and setCanvasCoords so it is easier to get [convert list of str to tuple of Decimal] and set [convert tuple of decimal to list of str]). This will simplify load and save (leaves in the settings OrderedDict will always have str for strings or Decimal, and int for integer, bool for bool).

Make a clean old-style dependencies.txt with no comments. Make a separate one for dependencies.windows.txt which starts with "-r dependencies.txt" and adds pywin32.

Make a folder in the canvas to be like the repo root (contain all commit-able stuff and possibly git-ignored stuff), named MultiLabelZ. In the metadata it should also be capitalized like MultiLabelZ. However, the repo URL should be all lowercase except Hierosoft.

Split up multilabelz.py code an replace it with a module folder. Make separate files for classes. Place only shareable constants and functions etc in `__init__.py` if any.

Add a runner script matching the structure of ones generated for commands by pip install. Place it in a "scripts" directory and before trying to import the module/file(s) use SCRIPTS_DIR = os.path.dirname(os.path.realpath(__file__)); sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
