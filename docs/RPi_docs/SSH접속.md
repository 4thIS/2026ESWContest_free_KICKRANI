# Pi 5 SSH 접속 가이드 (킥라니 `kick`)

> 2026-09-03 갱신. Pi hostname `kick` · user `admin` · 저장소 `~/embedded_kickboard`
> ⚠️ 같은 네트워크에 **다른 Pi(`webPi`)가 있음 — 건드리지 말 것.** `kick`은 우리 SSH 키가 통하는 기기로 식별.

## 1. 네트워크별 접속 (찬우 노트북 기준 별칭)

| 환경 | 명령 | 주소 | 비고 |
| --- | --- | --- | --- |
| **집 유선** (공유기 직결) | `ssh kick-home` | 192.168.79.8 | webPi는 .6 — 접근 금지 |
| **집 무선** (ssenu_Wi-Fi) | `ssh kick-wifi` | 192.168.79.9 | 유선 뽑아도 됨 |
| 연구실(712-5G) | IP 재확인 필요 | 이전 192.168.0.9x | 공유기 DHCP라 변동 |
| 폰 핫스팟 | `ssh kick-ip` | 192.168.79.17 | ⚠️ 집 대역과 같은 79.x — 혼동 주의 |
| 같은 네트워크·IP 모름 | `ssh kick-lan` | kick.local (mDNS) | Windows에서 간헐 실패 시 아래 §4 |
| ~~노트북 직결 랜선~~ | `kick-lan6`/`kick-cable` | — | 링크 플래핑으로 **비권장**(트러블슈팅 §세션2) |

별칭은 찬우 노트북 `~/.ssh/config`에 정의됨(키: `~/.ssh/id_ed25519_kick`).

## 2. Pi에 저장된 Wi-Fi 프로필 (모두 autoconnect — 부팅하면 알아서 붙음)

| SSID | 장소 | 비고 |
| --- | --- | --- |
| `ssenu_Wi-Fi` | 집 | 2026-09-03 등록. ⚠️ 비밀번호 끝에 `!` 있음 |
| `712-5G` | 연구실 | |
| `803-B-5G` | (기존) | netplan 프로필 |

새 Wi-Fi 추가(원격, passwordless sudo 설정됨):
```bash
sudo nmcli device wifi connect "<SSID>" password "<PW>"
# 'Secrets were required' 오류 시(WPA2/WPA3 혼용 공유기):
sudo nmcli connection modify "<SSID>" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<PW>"
sudo nmcli connection up "<SSID>"
```
기존 프로필은 삭제되지 않음(추가만 됨).

## 3. 다른 노트북에서 접속하기

```bash
ssh admin@<IP>            # 비밀번호 = Pi admin 계정 비밀번호
# 비밀번호 없이 쓰려면 (기기마다 자기 키 발급 — 개인키 복사 금지):
ssh-keygen -t ed25519
ssh-copy-id admin@<IP>    # Pi authorized_keys에 공개키 추가(여러 기기 공존 가능)
```

## 4. 새/모르는 네트워크에서 Pi 찾기

1. 노트북 IP·대역 확인 → 같은 /24에서 **포트 22 스캔**
2. 후보 IP마다 `ssh -o BatchMode=yes -i ~/.ssh/id_ed25519_kick admin@<IP> hostname`
   → **`kick`이 찍히는 기기만 우리 Pi** (webPi는 키 거부됨 — 안전한 식별법)
3. `kick.local` 핑/mDNS도 병용 (Windows에서 간헐적으로 이름 해석 실패 — 그땐 스캔)

## 5. 자주 쓰는 원격 명령

```bash
ssh kick-wifi 'cd ~/embedded_kickboard && git pull origin cw'   # 코드 최신화
ssh kick-wifi 'cd ~/embedded_kickboard/RPi && python3 -m pytest'
ssh kick-wifi 'sudo bash ~/embedded_kickboard/RPi/scripts/rfcomm_setup.sh'   # 앱 접속 준비(부팅마다)
ssh kick-wifi 'cd ~/embedded_kickboard/RPi && setsid nohup python3 -u -m pi.main --app --real > /tmp/app.log 2>&1 < /dev/null &'   # 통합 앱 상주 기동
ssh kick-wifi 'python3 ~/embedded_kickboard/RPi/scripts/estop.py'   # 🚨 비상정지
ssh kick-wifi 'vcgencmd get_throttled'   # 전원 판정(0x0=정상)
```

- 불안정한 링크에서 측정·모터 작업: 스크립트를 Pi에 `setsid nohup ... < /dev/null &`로 분리 실행 + 로그 회수 (모터 스크립트는 자체 시간제한 + `finally`/`atexit` 정지 필수)
- sudo: passwordless 설정됨(`/etc/sudoers.d/010-admin-nopasswd`, 2026-09-02)
