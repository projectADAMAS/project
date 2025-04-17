import cv2
import numpy as np
import module as htm
import time
import autopy
import math
import pyautogui
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# ========== Setup ==========
wCam, hCam = 640, 480
frameR = 100
smoothening = 5
movement_multiplier = 1.5  # Amplifies hand movement sensitivity

cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)

detector = htm.HandDetector(detectionCon=0.7, max_hands=1)
wScr, hScr = autopy.screen.size()

# Volume control setup
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume = cast(interface, POINTER(IAudioEndpointVolume))
minVol, maxVol = volume.GetVolumeRange()[0:2]

# ========== Variables ==========
plocX, plocY = 0, 0
clocX, clocY = 0, 0
volPer_prev = 0
click_state = False
pTime = 0
mode = "MOUSE"
last_toggle_time = 0
toggle_delay = 1.5  # seconds
last_fingers = [0, 0, 0, 0, 0]

# ========== Finger Detection ==========
def getFingersUp(lmList):
    fingers = []
    if len(lmList) == 0:
        return fingers
    if lmList[4][1] > lmList[3][1]:
        fingers.append(1)
    else:
        fingers.append(0)
    tip_ids = [8, 12, 16, 20]
    for tip in tip_ids:
        if lmList[tip][2] < lmList[tip - 2][2]:
            fingers.append(1)
        else:
            fingers.append(0)
    return fingers

# ========== Main Loop ==========
while True:
    success, img = cap.read()
    if not success or img is None:
        print("Camera error. Retrying...")
        time.sleep(0.1)
        continue

    img = detector.findHands(img)
    lmList = detector.findPosition(img, draw=False)

    if len(lmList) != 0:
        fingers = getFingersUp(lmList)

        # Mode toggle: Pinky curled (others up)
        current_time = time.time()
        if fingers == [1, 1, 1, 1, 0] and current_time - last_toggle_time > toggle_delay:
            mode = "VOLUME" if mode == "MOUSE" else "MOUSE"
            last_toggle_time = current_time

        last_fingers = fingers
    else:
        fingers = last_fingers

    # MOUSE MODE
    if mode == "MOUSE":
        if len(lmList) >= 9 and fingers == [0, 1, 0, 0, 0]:
            x1, y1 = lmList[8][1:]
            x3 = np.interp(x1, (frameR, wCam - frameR), (0, wScr * movement_multiplier))
            y3 = np.interp(y1, (frameR, hCam - frameR), (0, hScr * movement_multiplier))

            x3 = max(0, min(x3, wScr))
            y3 = max(0, min(y3, hScr))

            clocX = plocX + (x3 - plocX) / smoothening
            clocY = plocY + (y3 - plocY) / smoothening
            finalX = max(0, min(clocX, wScr - 1))
            finalY = max(0, min(hScr - clocY, hScr - 1))
            if abs(clocX - plocX) > 1 or abs(clocY - plocY) > 1:
                autopy.mouse.smooth_move(finalX, finalY)
                plocX, plocY = clocX, clocY
            cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)

        if len(lmList) >= 13 and fingers == [0, 1, 1, 0, 0]:
            if not click_state:
                autopy.mouse.click()
                click_state = True
                cv2.putText(img, "Click!", (500, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        else:
            click_state = False

    # VOLUME MODE
    elif mode == "VOLUME":
        if len(lmList) >= 9 and fingers[0] == 1 and fingers[1] == 1 and fingers[2] in [0, 1] and fingers[3] == 0 and fingers[4] == 0:
            x1, y1 = lmList[4][1:]
            x2, y2 = lmList[8][1:]
            length = math.hypot(x2 - x1, y2 - y1)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), 15, (255, 0, 255), cv2.FILLED)
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
            cv2.circle(img, (cx, cy), 15, (255, 0, 255), cv2.FILLED)

            volPer = np.interp(length, [30, 250], [0, 100])
            vol = np.interp(volPer, [0, 100], [minVol, maxVol])
            volume.SetMasterVolumeLevel(vol, None)
            volPer_prev = volPer

        # Peace sign (index + middle up, rest down)
        if fingers == [0, 1, 1, 0, 0]:
            if not click_state:
                pyautogui.press("space")
                click_state = True
                cv2.putText(img, "SPACEBAR", (400, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
        else:
            click_state = False

    if mode == "VOLUME":
        volBar = np.interp(volPer_prev, [0, 100], [400, 150])
        cv2.rectangle(img, (50, 150), (85, 400), (255, 0, 0), 3)
        cv2.rectangle(img, (50, int(volBar)), (85, 400), (255, 0, 0), cv2.FILLED)
        cv2.putText(img, f'{int(volPer_prev)}%', (40, 450), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 3)

    cv2.putText(img, f'MODE: {mode}', (400, 30), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 255), 2)
    cTime = time.time()
    fps = 1 / (cTime - pTime) if cTime != pTime else 0
    pTime = cTime
    cv2.putText(img, f'FPS: {int(fps)}', (500, 450), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 2)

    cv2.imshow("Hand Control", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

