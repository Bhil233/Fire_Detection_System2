import os
import time
from datetime import datetime

import cv2
from ultralytics import YOLO

# ================= Config =================
TARGET_OBJECT = "Fire"

# Confidence threshold (0.0 - 1.0)
CONF_THRESHOLD = 0.5

# Save settings
SAVE_DETECTED_FRAME = True
SAVE_DIR = "../fire_detection/backend/detected_frames"
MAX_SAVE_INTERVAL_SEC = 5.0
DEDUP_IOU_THRESHOLD = 0.7
NO_OBJECT_SAVE_INTERVAL_SEC = 10.0
# ==========================================


def box_iou(box_a, box_b):
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def is_same_target_set(current_boxes, saved_boxes, iou_threshold):
    if not current_boxes or not saved_boxes:
        return False
    if len(current_boxes) != len(saved_boxes):
        return False

    matched = [False] * len(saved_boxes)
    for cur in current_boxes:
        best_iou = 0.0
        best_idx = -1
        for idx, old in enumerate(saved_boxes):
            if matched[idx]:
                continue
            iou = box_iou(cur, old)
            if iou > best_iou:
                best_iou = iou
                best_idx = idx
        if best_idx < 0 or best_iou < iou_threshold:
            return False
        matched[best_idx] = True
    return True


def main():
    print(f"Loading model and searching for {TARGET_OBJECT} ...")
    model = YOLO("fire_test.pt")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        return

    print("Running")

    if SAVE_DETECTED_FRAME:
        os.makedirs(SAVE_DIR, exist_ok=True)

    last_detect_saved_time = 0.0
    last_saved_target_boxes = []
    last_no_object_saved_time = 0.0

    while True:
        success, frame = cap.read()
        if not success:
            break

        results = model(frame, stream=True, verbose=False, conf=CONF_THRESHOLD)

        object_found = False
        frame_to_save = None
        current_target_boxes = []

        for result in results:
            classes_detected = result.boxes.cls.cpu().numpy()
            boxes_xyxy = result.boxes.xyxy.cpu().numpy()

            for idx, cls_id in enumerate(classes_detected):
                class_name = result.names[int(cls_id)]
                if class_name == TARGET_OBJECT:
                    object_found = True
                    current_target_boxes.append([float(v) for v in boxes_xyxy[idx]])

            if object_found:
                # Save annotated image when target exists.
                frame_to_save = result.plot()

        if object_found:
            if SAVE_DETECTED_FRAME and frame_to_save is not None:
                now = time.time()
                interval_ok = (now - last_detect_saved_time) >= MAX_SAVE_INTERVAL_SEC
                duplicated = is_same_target_set(
                    current_target_boxes,
                    last_saved_target_boxes,
                    DEDUP_IOU_THRESHOLD,
                )
                if interval_ok and not duplicated:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    save_path = os.path.join(SAVE_DIR, f"{TARGET_OBJECT}_{timestamp}.jpg")
                    cv2.imwrite(save_path, frame_to_save)
                    last_detect_saved_time = now
                    last_saved_target_boxes = current_target_boxes
        else:
            last_saved_target_boxes = []
            if SAVE_DETECTED_FRAME:
                now = time.time()
                if (now - last_no_object_saved_time) >= NO_OBJECT_SAVE_INTERVAL_SEC:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    save_path = os.path.join(SAVE_DIR, f"no_object_{timestamp}.jpg")
                    cv2.imwrite(save_path, frame)
                    last_no_object_saved_time = now

        cv2.imshow("YOLO Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
