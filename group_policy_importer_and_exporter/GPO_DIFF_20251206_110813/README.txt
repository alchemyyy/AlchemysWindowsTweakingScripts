GROUP POLICY DIFF EXPORT
========================

Export Date: Sat 12/06/2025 11:08:21.10
Computer: DESKTOP-J8EJ3AM
User: Alchemy

CONTENTS:
---------
- policies_hklm.reg: HKLM Software Policies
- policies_hkcu.reg: HKCU Software Policies  
- policies_cv_hklm.reg: HKLM CurrentVersion Policies
- policies_cv_hkcu.reg: HKCU CurrentVersion Policies
- policies_ms_hklm.reg: HKLM Microsoft Policies
- policies_ms_hkcu.reg: HKCU Microsoft Policies
- security_policy.inf: Local Security Policy
- gpresult.html: Full Group Policy Results Report
- IMPORT_GPO_DIFF.bat: Import script

IMPORT INSTRUCTIONS:
--------------------
1. Copy this entire folder to the target system
2. Run IMPORT_GPO_DIFF.bat as Administrator
3. Restart the system for all changes to take effect

NOTES:
------
- This export contains only configured policy settings
- Import on a fresh Windows install will apply these policies
- Domain GPOs will override local policies
- Review gpresult.html for complete applied policy details
