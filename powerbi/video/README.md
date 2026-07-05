# Walkthrough video

`compass-walkthrough-captioned.mp4` (~3:25, 1920×1032, captioned, silent) is
produced from code like everything else in this repository:

1. `video_actions.ps1` — drives Power BI Desktop on an absolute-time schedule
   (page changes, hovers, the live row-level-security switch to Advisor_ADV01)
   while ffmpeg records the screen.
2. `captions.ass` — the narration as styled subtitles, timed to the same
   schedule, burned in with ffmpeg.

```powershell
# record (Power BI Desktop open on the compass project, screen clear)
ffmpeg -y -f gdigrab -framerate 30 -i desktop -t 205 -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p raw.mp4
# in parallel: powershell -File video_actions.ps1
# then burn captions and trim the taskbar
ffmpeg -y -i raw.mp4 -vf "crop=1920:1032:0:0,subtitles=captions.ass" -c:v libx264 -preset veryfast -crf 21 -movflags +faststart compass-walkthrough-captioned.mp4
```

`raw.mp4` (uncaptioned) is kept locally for recording a voiceover version.
MP4s are gitignored — host the final video (YouTube unlisted / Loom) and link
it from the main README.
