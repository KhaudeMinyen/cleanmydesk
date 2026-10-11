=====================================================================
  CLEANMYDESK
  AI-Assisted Desk Organization Application
=====================================================================

Project type : Artificial Intelligence merit badge project (design phase)
Status       : Planning / outline only. No code has been written yet.
Platforms    : Windows, macOS, and Linux (one codebase)
Repository   : khaudeminyen/cleanmydesk


---------------------------------------------------------------------
1. WHAT IS CLEANMYDESK?
---------------------------------------------------------------------

CleanMyDesk is a desktop application that suggests how to arrange the
items on a desk. It looks at three things:

  a) THE DESK      - how big the desk is, and where things can go.
  b) THE OBJECTS   - how big each item on the desk is (monitor,
                     keyboard, mug, phone, notebook, and so on).
  c) THE USER      - how the person works: which items they reach for
                     most, whether they are left- or right-handed, and
                     what tasks they do at the desk.

From those inputs, the app produces a suggested layout drawn as a
top-down diagram, along with a plain-language explanation for every
recommended move. For example:

  "Move your phone to the left side of the desk. You are right-handed,
   and you pick up your phone about 40 times a day. Keeping it on the
   left stops you from reaching across your keyboard."


---------------------------------------------------------------------
2. WHY IT USES AI
---------------------------------------------------------------------

The problem has no single correct answer. Each person's desk, habits,
and priorities are different, so the app has to weigh many factors and
learn from feedback. The AI parts of the project are:

  - Object recognition  : a camera photo of the desk is analyzed to find
                          and label items (for example, "laptop",
                          "cup", "phone").
  - Size estimation     : the app estimates each item's real-world size
                          using a known reference marker in the photo.
  - Layout optimization : a search algorithm tries many arrangements
                          and scores each one for reach, comfort, and
                          fit. It keeps the best-scoring arrangement.
  - Habit learning      : the app learns the user's preferences over
                          time from which suggestions they accept or
                          reject.
  - Explanations        : each suggestion comes with the reasons behind
                          it, so the user can understand and trust it.


---------------------------------------------------------------------
3. OUTLINE OF THE APPLICATION
---------------------------------------------------------------------

3.1  Main screens
  [1] Welcome / Home        - start a new desk, or open a saved desk.
  [2] Desk Setup            - enter the desk width and depth (or
                              calibrate with a camera).
  [3] Item Inventory        - list of items on the desk, each with a
                              name, category, size, and how often it
                              is used.
  [4] Work Profile          - short questionnaire about the user's
                              habits (see section 4).
  [5] Suggestion View       - top-down diagram of the current desk
                              next to the suggested layout, with a
                              list of moves.
  [6] Feedback              - accept, reject, or adjust each move.
                              This feeds the learning module.
  [7] Settings              - units (cm or inches), camera choice,
                              privacy options, and data export/delete.

3.2  Core features
  F1. Desk definition        Enter desk size, or detect it from a photo.
  F2. Item entry             Add items by hand, or detect them from a
                             camera photo and confirm or edit the result.
  F3. Size calibration       Use a printed marker of known size (for
                             example, an ArUco marker) placed on the
                             desk so the app can convert pixels into
                             centimeters or inches.
  F4. Work profile           Store the user's handedness, main tasks,
                             and usage frequency for each item.
  F5. Layout suggestion      Generate one or more improved layouts.
  F6. Explanation panel      Show the reason for each suggested move.
  F7. Before/after view      Side-by-side or slider comparison.
  F8. Learning from feedback Adjust future suggestions based on what the
                             user accepted or rejected.
  F9. Save and export        Save desks and layouts. Export a layout as
                             an image or PDF.
  F10. Reminders (optional)  Suggest a tidy-up schedule.

3.3  Design zones (the "reach map")
  The desk is split into zones, each with a score that reflects how
  easy it is to reach from the user's seat:

    Zone 1 - Core      : directly in front of the user (keyboard and
                         main screen area). Best for items used all day.
    Zone 2 - Reach     : within an arm's reach on either side. Best for
                         frequently used items.
    Zone 3 - Stretch   : toward the back or far edges. Best for items
                         used occasionally.
    Zone 4 - Storage   : off the desk entirely. Best for rarely used
                         items.

  Handedness changes the scores. For a right-handed user, items used
  often are placed further to the right. For a left-handed user, they
  are placed further to the left.


---------------------------------------------------------------------
4. INPUTS
---------------------------------------------------------------------

4.1  Desk
  - Width, depth, and (optional) height of the surface
  - Shape: rectangle (version 1), corner or L-shape (later version)
  - Obstacles: outlets, drawers, or a window to one side (optional)

4.2  Objects
  - Name
  - Category (screen, input device, writing, drink, phone, paper,
    personal item, and so on)
  - Width, depth, and height
  - Usage frequency: rarely, sometimes, often, or constantly
  - Fixed flag: items that must stay where they are (for example, a
    monitor that is mounted)

4.3  Work habits (Work Profile questionnaire)
  - Handedness: left, right, or either
  - Primary tasks: typing, writing by hand, reading, video calls,
    drawing, or gaming
  - Sitting or standing desk
  - Screen count (one or two)
  - Dislikes: for example, "I never want my phone within reach."
  - Optional usage log: times per day each item is used (entered by
    hand, or tracked with the user's permission in later versions)


---------------------------------------------------------------------
5. HOW THE SUGGESTION ENGINE WORKS
---------------------------------------------------------------------

Step 1  Build the model     Turn the desk, items, and profile into a
                            top-down model with coordinates in
                            centimeters.

Step 2  Score a layout      Each layout gets a total score made of:
                              + Reach score    (frequent items in easy zones)
                              + Fit score      (no overlaps, inside the desk)
                              + Clearance      (space for keyboard and mouse)
                              + Handedness     (match with the user's hand)
                              + Preference     (learned from feedback)
                              - Penalty        (items that move too far
                                                from their current spot)

Step 3  Search              Start from the current layout. Try random
                            small changes (move, swap, or rotate an
                            item). Keep changes that raise the score.
                            Use simulated annealing so the search can
                            escape weak local answers.

Step 4  Explain             For each change in the final layout, write
                            the reason in plain language, using the
                            score terms that drove the change.

Step 5  Learn               When the user accepts a suggestion, its
                            features are rewarded. When they reject it,
                            those features are penalized. The weights
                            in Step 2 are adjusted over time.


---------------------------------------------------------------------
6. OBJECT RECOGNITION PIPELINE (camera mode)
---------------------------------------------------------------------

  1. Capture   The user takes a photo of the desk with a reference
               marker in view.
  2. Detect    A pre-trained vision model finds the objects and labels
               them with a confidence score.
  3. Measure   The marker's known size converts the detected boxes into
               real-world width and depth.
  4. Confirm   The user checks the list, renames items, fixes sizes,
               and removes false detections. The app never trusts a
               detection without confirmation.

  Fallback: if the camera is not available or the detection is poor,
  the user enters the items by hand. The app works fully without a
  camera.


---------------------------------------------------------------------
7. TECHNOLOGY CHOICES (proposed)
---------------------------------------------------------------------

  Language           Python 3.11 or newer (readable, and has strong
                     AI libraries)
  User interface     PySide6 (Qt for Python). Runs the same on Windows,
                     macOS, and Linux.
  Drawing the desk   Qt graphics view (2D canvas)
  Camera and vision  OpenCV (camera capture, ArUco marker detection)
  Object detection   A small pre-trained detection model (for example,
                     YOLO family, run locally with ONNX Runtime)
  Optimization       Plain Python with NumPy. Simulated annealing is a
                     short algorithm, so no large framework is needed.
  Data storage       SQLite (a single local file per user)
  Testing            pytest
  Packaging          PyInstaller, built once per operating system

  Note: Object detection uses a pre-trained model. The project does not
  train a new model from scratch. Training is a stretch goal.


---------------------------------------------------------------------
8. HOW THE PROJECT IS ORGANIZED (planned folder layout)
---------------------------------------------------------------------

  cleanmydesk/
    readme.txt          this file
    LICENSE
    src/
      cleanmydesk/
        ui/             screens and widgets (PySide6)
        model/          desk, item, and profile classes
        vision/         camera capture, marker detection, object detection
        engine/         scoring, layout search, explanations
        learning/       feedback storage and weight updates
        storage/        SQLite access
    tests/              unit tests for the scoring and search code
    docs/               design notes and diagrams
    assets/             icons and sample desks for testing


---------------------------------------------------------------------
9. DATA AND PRIVACY
---------------------------------------------------------------------

  - All data stays on the user's computer. Nothing is uploaded.
  - Camera photos are used only to detect items. They are deleted
    after the user confirms the item list, unless the user chooses to
    keep them.
  - The user can view, export, and delete all stored data from the
    Settings screen.
  - The app asks for camera permission only when the user chooses the
    camera mode.


---------------------------------------------------------------------
10. DEVELOPMENT PLAN (milestones)
---------------------------------------------------------------------

  Milestone 1  Model and rules
               Desk, item, and profile classes. Score a hand-made
               layout. Unit tests pass.

  Milestone 2  Suggestion engine
               Layout search with simulated annealing. Explanations
               for each move. Command-line demo.

  Milestone 3  Desktop interface
               Screens F1 to F7 with manual entry only.

  Milestone 4  Camera and vision
               Marker calibration, object detection, and the confirm
               step.

  Milestone 5  Learning and saving
               Feedback screen, weight updates, SQLite storage, and
               export.

  Milestone 6  Packaging and testing
               Test on Windows, macOS, and Linux. Build installers or
               standalone files for each platform.


---------------------------------------------------------------------
11. TESTING PLAN
---------------------------------------------------------------------

  - Unit tests    Scoring rules, overlap checks, zone assignment.
  - Search tests  Known desks with known good answers (for example, a
                  phone should never be placed in Zone 1 for a user who
                  never uses it).
  - Vision tests  A set of sample desk photos with the correct item
                  lists. Measure how many items are found correctly.
  - User tests    Ask 3 to 5 people to use the app and rate each
                  suggestion as helpful or not helpful.
  - Platform      The same test suite runs on all three operating systems.


---------------------------------------------------------------------
12. RISKS AND HOW WE PLAN TO HANDLE THEM
---------------------------------------------------------------------

  Risk                              Plan
  --------------------------------  ----------------------------------
  Detection misses or mislabels     Always confirm with the user. Let
  items                             them edit everything. Manual entry
                                    always works.

  Size estimates are off            Calibrate with a marker. Show the
                                    measured size and let the user
                                    correct it.

  Suggestions feel random           Explain every move. Start with a
                                    simple, transparent scoring rule.

  Camera is not available           Manual entry mode is complete on its
                                    own.

  Packaging differs by OS           Test each platform early, not just
                                    at the end.


---------------------------------------------------------------------
13. STRETCH GOALS
---------------------------------------------------------------------

  - L-shaped and corner desks
  - Standing-desk mode with height changes
  - Cable management suggestions
  - A short daily "reset" checklist
  - A natural-language question box, such as "Where should my
    water bottle go?"


---------------------------------------------------------------------
14. GLOSSARY
---------------------------------------------------------------------

  Artificial intelligence (AI)
      Computer methods that make decisions or predictions from data.
  Object detection
      Finding and naming objects in a photo.
  ArUco marker
      A square black-and-white pattern that a camera can detect
      precisely. Used here as a size reference.
  Simulated annealing
      A search method that sometimes accepts a worse answer early on,
      so it can find a better overall answer later.
  Reach zone
      An area of the desk, grouped by how easily the user can get to it.
  Feedback loop
      A cycle where the app's results influence its future results.


---------------------------------------------------------------------
15. HOW TO READ THIS PROJECT
---------------------------------------------------------------------

  This project is currently a plan. The next step is Milestone 1:
  building the desk, item, and profile classes, plus their tests.
  No application code exists in the repository yet.

=====================================================================
  End of readme.txt
=====================================================================
