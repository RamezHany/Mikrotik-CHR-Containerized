# Default configuration for Ramez's MikroTik Branding Maker package (.rsc).
# Upload this file as the branding package's "Default configuration".
# Per MikroTik docs: it runs when the branding package is installed, and
# after /system reset-configuration ONLY this file is applied (the stock
# defconfig is replaced) — so the ramez login survives resets in every
# deployment of the image.
#
# Owner decision 2026-11-12: the image opens ONLY with his branding and the
# login ramez / ramez. The built-in admin account is therefore disabled
# (ramez is created first, in the same run, so there is no lockout).

/system identity set name=RouterOS

# The branded default admin
/user add name=ramez group=full password="ramez" comment="branding default admin"
/user set admin disabled=yes

# Service hardening for a fresh deployment
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=no
/ip service set ssh disabled=no
/ip service set api disabled=no
/ip service set api-ssl disabled=yes
