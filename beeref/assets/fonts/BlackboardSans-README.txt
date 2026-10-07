Blackboard Sans is a changed copy of Selawik 1.01, the font Microsoft
publishes to stand in for Segoe UI (https://github.com/microsoft/Selawik).
It is used, and its changes are passed on, under the SIL Open Font
License 1.1; see BlackboardSans-OFL.txt, which is Selawik's own licence
file as it came.

What was changed, by tools/make_note_font.py:

- The ascender and descender in the hhea table are set to the Windows
  values of the font's own OS/2 table (2210 and -514, from 2027 and
  -431), so a line is as tall on a Mac as it is on Windows.
- The font is named Blackboard Sans: the licence keeps the name Selawik
  for the original.
- The digital signature, which was true of the original only, is left
  out.
