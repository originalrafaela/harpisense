// Navigation intent only. ConfigManager remains the sole owner of editable data.
let pending=false;
export function openCloudBackup(){pending=true;location.hash='settings';window.dispatchEvent(new Event('harpisense:configure-cloud-backup'))}
export function consumeCloudBackupIntent(){const value=pending;pending=false;return value}
