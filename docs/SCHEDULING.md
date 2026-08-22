# Scheduling

The bot is designed to run once per day. It tracks prepared applications in `data/applications_ledger.jsonl`, so rerunning it on the same day will not duplicate the same job.

## macOS LaunchAgent

Create `~/Library/LaunchAgents/com.local.jobs-applications-bot.plist` with your local paths:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.local.jobs-applications-bot</string>

  <key>WorkingDirectory</key>
  <string>/Users/almonderzoubi/Desktop/jobs_applications_bot</string>

  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-m</string>
    <string>job_bot.run_daily</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/tmp/jobs-applications-bot.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/jobs-applications-bot.err.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.local.jobs-applications-bot.plist
```

## Linux Cron

Run at 9:00 every morning:

```cron
0 9 * * * cd /Users/almonderzoubi/Desktop/jobs_applications_bot && python3 -m job_bot.run_daily >> /tmp/jobs-applications-bot.log 2>&1
```
