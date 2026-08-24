#!/usr/bin/env bash
# Pi에서 앱(RFCOMM/SPP) 접속 준비 — 1회 실행(부팅마다). 계약 2 · pi/comm/rfcomm_server.py
#   sudo bash scripts/rfcomm_setup.sh
# 하는 일:
#   1) bluetoothd를 호환 모드(-C)로 → sdptool 사용 가능 (Pi OS 기본은 -C 없음)
#   2) SDP에 Serial Port(UUID 00001101) 채널 1 등록 → 앱 createRfcommSocketToServiceRecord가 찾음
#   3) 어댑터 discoverable/pairable ON (첫 페어링용)
set -euo pipefail
CH=${1:-1}

if ! grep -q -- '-C' /lib/systemd/system/bluetooth.service; then
  echo "[setup] bluetoothd 호환 모드(-C) 활성화"
  sudo sed -i 's|^ExecStart=/usr/libexec/bluetooth/bluetoothd$|ExecStart=/usr/libexec/bluetooth/bluetoothd -C|' \
    /lib/systemd/system/bluetooth.service
  sudo systemctl daemon-reload
  sudo systemctl restart bluetooth
  sleep 2
fi

sudo chmod 777 /var/run/sdp 2>/dev/null || true
sudo sdptool add --channel="$CH" SP && echo "[setup] SDP: Serial Port 채널 $CH 등록"

bluetoothctl power on >/dev/null
bluetoothctl discoverable on >/dev/null
bluetoothctl pairable on >/dev/null
echo "[setup] discoverable/pairable ON — 앱에서 페어링 후 접속. 이름: $(bluetoothctl show | awk '/Alias/{print $2}')"
echo "[setup] 이제:  python -m pi.main --app --real"
