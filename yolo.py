# import the necessary packages
import numpy as np
import time
from scipy import spatial
import cv2
import os

# All these classes will be counted as 'vehicles'
list_of_vehicles = ["bicycle", "car", "motorbike", "bus", "truck", "train"]
# Setting the threshold for the number of frames to search a vehicle for
FRAMES_BEFORE_CURRENT = 10
inputWidth, inputHeight = 416, 416

LABELS = open("yolo_config/coco.names").read().strip().split("\n")
weightsPath = "yolo_config/yolov3.weights"
configPath = "yolo_config/yolov3.cfg"
inputVideoPath = "videos/car2.mp4"
outputVideoPath = "out_videos/car2.avi"
preDefinedConfidence = 0.5
preDefinedThreshold = 0.3
USE_GPU = False

# Initialize a list of colors to represent each possible class label
np.random.seed(42)
COLORS = np.random.randint(0, 255, size=(len(LABELS), 3),
                           dtype="uint8")



def displayVehicleCount(frame, vehicle_count):
    cv2.putText(
        frame,  # Image
        'Detected Vehicles: ' + str(vehicle_count),  # Label
        (20, 20),  # Position
        cv2.FONT_HERSHEY_SIMPLEX,  # Font
        0.8,  # Size
        (0, 0xFF, 0),  # Color
        2,  # Thickness
        cv2.FONT_HERSHEY_COMPLEX_SMALL,
    )


def displayFPS(start_time, num_frames):
    current_time = int(time.time())
    if (current_time > start_time):
        os.system('clear')  # Equivalent of CTRL+L on the terminal
        print("FPS:", num_frames)
        num_frames = 0
        start_time = current_time
    return start_time, num_frames


def drawDetectionBoxes(idxs, boxes, classIDs, confidences, frame):
    # ensure at least one detection exists
    if len(idxs) > 0:
        # loop over the indices we are keeping
        for i in idxs.flatten():
            # extract the bounding box coordinates
            (x, y) = (boxes[i][0], boxes[i][1])
            (w, h) = (boxes[i][2], boxes[i][3])

            # draw a bounding box rectangle and label on the frame
            color = [int(c) for c in COLORS[classIDs[i]]]
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            text = "{}: {:.4f}".format(LABELS[classIDs[i]],
                                       confidences[i])
            cv2.putText(frame, text, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            # Draw a green dot in the middle of the box
            cv2.circle(frame, (x + (w // 2), y + (h // 2)), 2, (0, 0xFF, 0), thickness=2)


def initializeVideoWriter(video_width, video_height, videoStream):
    # Getting the fps of the source video
    sourceVideofps = videoStream.get(cv2.CAP_PROP_FPS)
    # initialize our video writer
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    return cv2.VideoWriter(outputVideoPath, fourcc, sourceVideofps,
                           (video_width, video_height), True)


def boxInPreviousFrames(previous_frame_detections, current_box, current_detections):
    centerX, centerY, width, height = current_box
    dist = np.inf  # Initializing the minimum distance
    # Iterating through all the k-dimensional trees
    for i in range(FRAMES_BEFORE_CURRENT):
        coordinate_list = list(previous_frame_detections[i].keys())
        if len(coordinate_list) == 0:  # When there are no detections in the previous frame
            continue
        # Finding the distance to the closest point and the index
        temp_dist, index = spatial.KDTree(coordinate_list).query([(centerX, centerY)])
        if (temp_dist < dist):
            dist = temp_dist
            frame_num = i
            coord = coordinate_list[index[0]]

    if (dist > (max(width, height) / 2)):
        return False

    # Keeping the vehicle ID constant
    current_detections[(centerX, centerY)] = previous_frame_detections[frame_num][coord]
    return True


def count_vehicles(idxs, boxes, classIDs, vehicle_count, previous_frame_detections, frame):
    current_detections = {}
    # ensure at least one detection exists
    if len(idxs) > 0:
        # loop over the indices we are keeping
        for i in idxs.flatten():
            # extract the bounding box coordinates
            (x, y) = (boxes[i][0], boxes[i][1])
            (w, h) = (boxes[i][2], boxes[i][3])

            centerX = x + (w // 2)
            centerY = y + (h // 2)


            if (LABELS[classIDs[i]] in list_of_vehicles):
                current_detections[(centerX, centerY)] = vehicle_count
                if (not boxInPreviousFrames(previous_frame_detections, (centerX, centerY, w, h), current_detections)):
                    vehicle_count += 1

                ID = current_detections.get((centerX, centerY))

                if (list(current_detections.values()).count(ID) > 1):
                    current_detections[(centerX, centerY)] = vehicle_count
                    vehicle_count += 1

                # Display the ID at the center of the box
                cv2.putText(frame, str(ID), (centerX, centerY), \
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, [0, 0, 255], 2)

    return vehicle_count, current_detections



print("[INFO] loading YOLO from disk...")
net = cv2.dnn.readNetFromDarknet(configPath, weightsPath)

# Using GPU if flag is passed
if USE_GPU:
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

ln = net.getLayerNames()
ln = [ln[i[0] - 1] for i in net.getUnconnectedOutLayers()]

# initialize the video stream, pointer to output video file, and
# frame dimensions
videoStream = cv2.VideoCapture(inputVideoPath)
video_width = int(videoStream.get(cv2.CAP_PROP_FRAME_WIDTH))
video_height = int(videoStream.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Specifying coordinates for a default line
x1_line = 0
y1_line = video_height // 2
x2_line = video_width
y2_line = video_height // 2

# Initialization
previous_frame_detections = [{(0, 0): 0} for i in range(FRAMES_BEFORE_CURRENT)]
# previous_frame_detections = [spatial.KDTree([(0,0)])]*FRAMES_BEFORE_CURRENT # Initializing all trees
num_frames, vehicle_count = 0, 0
writer = initializeVideoWriter(video_width, video_height, videoStream)
start_time = int(time.time())
# loop over frames from the video file stream
while True:
    print("================NEW FRAME================")
    num_frames += 1
    print("FRAME:\t", num_frames)
    # Initialization for each iteration
    boxes, confidences, classIDs = [], [], []
    vehicle_crossed_line_flag = False

    # Calculating fps each second
    start_time, num_frames = displayFPS(start_time, num_frames)
    # read the next frame from the file
    (grabbed, frame) = videoStream.read()

    # if the frame was not grabbed, then we have reached the end of the stream
    if not grabbed:
        break


    blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (inputWidth, inputHeight),
                                 swapRB=True, crop=False)
    net.setInput(blob)
    start = time.time()
    layerOutputs = net.forward(ln)
    end = time.time()

    # loop over each of the layer outputs
    for output in layerOutputs:
        # loop over each of the detections
        for i, detection in enumerate(output):
            # extract the class ID and confidence (i.e., probability)
            # of the current object detection
            scores = detection[5:]
            classID = np.argmax(scores)
            confidence = scores[classID]


            if confidence > preDefinedConfidence:

                box = detection[0:4] * np.array([video_width, video_height, video_width, video_height])
                (centerX, centerY, width, height) = box.astype("int")

                # use the center (x, y)-coordinates to derive the top
                # and and left corner of the bounding box
                x = int(centerX - (width / 2))
                y = int(centerY - (height / 2))


                boxes.append([x, y, int(width), int(height)])
                confidences.append(float(confidence))
                classIDs.append(classID)


    idxs = cv2.dnn.NMSBoxes(boxes, confidences, preDefinedConfidence,
                            preDefinedThreshold)

    # Draw detection box
    drawDetectionBoxes(idxs, boxes, classIDs, confidences, frame)

    vehicle_count, current_detections = count_vehicles(idxs, boxes, classIDs, vehicle_count, previous_frame_detections,
                                                       frame)

    # Display Vehicle Count if a vehicle has passed the line
    displayVehicleCount(frame, vehicle_count)

    # write the output frame to disk
    writer.write(frame)

    cv2.imshow('Frame', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    # Updating with the current frame detections
    previous_frame_detections.pop(0)  # Removing the first frame from the list
    # previous_frame_detections.append(spatial.KDTree(current_detections))
    previous_frame_detections.append(current_detections)

# release the file pointers
print("[INFO] cleaning up...")
writer.release()
videoStream.release()