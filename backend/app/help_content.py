"""US-19: the approved help articles the chatbot may answer from (seeded into the database)."""

ARTICLES = [
    ("Reset a forgotten password",
     "password reset forgot forgotten change expired login sign in",
     "1. Go to the sign-in page and choose **Forgot password**.\n"
     "2. Enter your work email address and follow the link sent to your inbox (check spam if it doesn't arrive within 5 minutes).\n"
     "3. Choose a new password of at least 12 characters that you haven't used before.\n"
     "4. Sign in again on every device, including your phone's email app.\n"
     "Never share your password or a one-time code with anyone, including support staff."),
    ("Unlock an account after too many sign-in attempts",
     "locked lockout locked out too many attempts account disabled",
     "Accounts lock for 15 minutes after 5 failed sign-in attempts.\n"
     "1. Wait 15 minutes, then sign in with your current password.\n"
     "2. If you've forgotten the password, use **Forgot password** instead of retrying.\n"
     "3. If the account is still locked after 15 minutes, or you didn't make the failed attempts yourself, submit a ticket in **Account Access** so an agent can check it."),
    ("Set up or replace multi-factor authentication (MFA)",
     "mfa 2fa two factor authenticator app code new phone token verification",
     "1. Install the Microsoft Authenticator app on your phone.\n"
     "2. Sign in at the security info page and choose **Add sign-in method > Authenticator app**, then scan the QR code.\n"
     "3. Approve the test notification to finish.\n"
     "**Got a new phone?** Add the new device before wiping the old one. If you no longer have the old phone, submit a ticket in **Account Access**; an agent must verify your identity before resetting MFA."),
    ("Fix VPN disconnects and connection problems",
     "vpn disconnect disconnects dropping drops connect remote home tunnel globalprotect",
     "1. Make sure you're on VPN client version 5.3 or later (Help > About). Version 5.2.x has a known keep-alive bug that drops connections every few minutes.\n"
     "2. Restart your home router, then reconnect the VPN.\n"
     "3. If you're on Wi-Fi, try a wired connection or a phone hotspot to rule out the home network.\n"
     "4. Sign out of the VPN client completely and sign back in.\n"
     "If drops continue on the latest version, submit a ticket in **Network** with the times it disconnected."),
    ("Connect to office Wi-Fi",
     "wifi wi-fi wireless network internet office connect slow guest",
     "1. Choose the **Corp-Secure** network (not Corp-Guest).\n"
     "2. Sign in with your full work email address and password.\n"
     "3. If you're prompted about a certificate, accept the one issued to *radius.corp.local*.\n"
     "4. If it keeps asking for your password, choose **Forget this network** and connect again.\n"
     "Guests should use Corp-Guest with the daily code shown at reception."),
    ("Laptop won't turn on or charge",
     "laptop power turn on boot charge charging battery dead black screen won't start",
     "1. Plug in the original charger and check that the charging light comes on. Try a different outlet.\n"
     "2. Hold the power button for 30 seconds to drain residual power, then press it once normally.\n"
     "3. Disconnect docks, USB devices and external monitors and try again.\n"
     "4. If the power light blinks a code or nothing happens at all, submit a ticket in **Hardware** with the laptop's asset tag. Don't open the case yourself."),
    ("Printer is offline or jammed",
     "printer print printing offline jam jammed queue toner paper",
     "1. Check the printer's display for a paper jam or empty tray, and clear it following the diagram on the panel.\n"
     "2. On your computer, open **Printers & scanners**, select the printer and choose **Open queue > Cancel all documents**, then print again.\n"
     "3. Remove and re-add the printer from **Add a printer** if it still shows Offline.\n"
     "4. For toner or hardware faults shown on the printer itself, submit a ticket in **Hardware** with the printer's name."),
    ("Request new software or a license",
     "software install license licence application request adobe acrobat new app approval",
     "1. Check the **Company Portal** app first: most approved software installs from there in one click, without admin rights.\n"
     "2. For paid software (for example Adobe Acrobat Pro), submit a ticket in **Software** with the product name and the business reason. Your manager's approval is requested automatically.\n"
     "3. Installs typically complete within 2 business days of approval."),
    ("Set up work email on a phone",
     "email mail outlook phone mobile iphone android setup calendar",
     "1. Install the Outlook app from your phone's app store.\n"
     "2. Add your account with your full work email address and approve the MFA prompt.\n"
     "3. If asked, allow the Company Portal to register the device; email won't sync until it does.\n"
     "Built-in mail apps aren't supported for work email."),
    ("Application crashes or shows an error",
     "crash crashes crashing error freeze frozen not responding application app slow update excel word powerpoint teams outlook",
     "1. Save your work, close the application completely and reopen it.\n"
     "2. Restart your computer; pending updates often cause crashes.\n"
     "3. Install updates from **Company Portal > Updates**.\n"
     "4. If it still fails, take a screenshot of the exact error message and submit a ticket in **Software** with the app name and version."),
]
