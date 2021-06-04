#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# import the necessary packages
# from keras.applications import ResNet50
from keras.applications import imagenet_utils
import numpy as np
import settings
import helpers
import redis
import time
import json
from keras.models import load_model
import io
from PIL import Image
from tool.config import Cfg
import torch
from tool.predictor import Predictor
import cv2
import base64

# connect to Redis server
db = redis.StrictRedis(host=settings.REDIS_HOST,
	port=settings.REDIS_PORT, db=settings.REDIS_DB)

def get_output_layers(net):
    layer_names = net.getLayerNames()

    output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]

    return output_layers


def pred_orientation(img, model, img_size):
    img = resize_pad(img,img_size).astype(np.float32)/255
    img = np.expand_dims(img, axis=0)
    pred = model.predict(img)
    pred = np.argmax(pred)
    return pred

def pred_info(net, images, classes, model_orientation, classes_orientation, detector):
    # truyền nhiều ảnh 
	results_yolo = []
	for image in images:
		Width = image.shape[1]
		Height = image.shape[0]
		mc = image.copy()
		scale = 0.00392
		blob = cv2.dnn.blobFromImage(image, scale, (608, 608), (0, 0, 0), True, crop=False)
		net.setInput(blob)
		outs = net.forward(get_output_layers(net))
		print("hahahahah", outs)
		class_ids = []
		confidences = []
		boxes = []
		conf_threshold = 0.5
		nms_threshold = 0.4

		for out in outs:
			for detection in out:
				scores = detection[5:]
				class_id = np.argmax(scores)
				confidence = scores[class_id]
				if confidence > 0.5:
					center_x = int(detection[0] * Width)
					center_y = int(detection[1] * Height)
					w = int(detection[2] * Width)
					h = int(detection[3] * Height)
					x = center_x - w / 2
					y = center_y - h / 2
					class_ids.append(class_id)
					confidences.append(float(confidence))
					boxes.append([x, y, w, h])

		indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
		results = []
		seller = []
		address = []
		timestamp = []
		total_cost = []
		for i in indices:
			i = i[0]
			box = boxes[i]
			x = box[0]
			y = box[1]
			w = box[2]
			h = box[3]
			img = mc[int(y):int(y+h), int(x):int(x+w),:]
			# print(img.shape)
			class_id = class_ids[i]
			label = str(classes[class_id])
			orientation = classes_orientation[pred_orientation(img, model_orientation, img_size=96)]
			# print(label, orientation)
			if orientation == "rotate_90":
				img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
			elif orientation == "rotate_270":
				img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
			elif orientation == "rotate_180":
				img = cv2.rotate(img, cv2.ROTATE_180)
			else:
				img = img
			# cv2.imwrite("b.jpg", (img*255).astype(np.uint8))
			img = Image.fromarray((img*255).astype(np.uint8))
			s = detector.predict(img)
			# img = np.array(img)
			cv2.rectangle(mc, (int(x), int(y)), (int(x+w), int(y+h)), (0,255,0), 1)
			# cv2.putText(mc, label+": "+s, (int(x - 5), int(y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,255,0), 1)
			# results.append((img, label, box))
			if label=="SELLER":
				seller.append(s)
			elif label=="ADDRESS":
				address.append(s)
			elif label=="TIMESTAMP":
				timestamp.append(s)
			else:
				total_cost.append(s)
		results_yolo.append((mc, seller, address,timestamp, total_cost))
	return results_yolo

def resize_pad(im, img_size):
    old_size = im.shape[:2] # old_size is in (height, width) format

    ratio = float(img_size)/max(old_size)
    new_size = tuple([int(x*ratio) for x in old_size])

    # new_size should be in (width, height) format

    im = cv2.resize(im, (new_size[1], new_size[0]))

    delta_w = img_size - new_size[1]
    delta_h = img_size - new_size[0]
    top, bottom = delta_h//2, delta_h-(delta_h//2)
    left, right = delta_w//2, delta_w-(delta_w//2)

    color = [0, 0, 0]
    new_im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT,
        value=color)
    return new_im

def classify_process():
	# load the pre-trained Keras model (here we are using a model
	# pre-trained on ImageNet and provided by Keras, but you can
	# substitute in your own networks just as easily)
	print("* Loading model...")
	# model = ResNet50(weights="imagenet")
	# print("* Model loaded")

     # load model recor
	config = Cfg.load_config_from_name('vgg_transformer')
	config['vocab'] = 'aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆfFgGhHiIìÌỉỈĩĨíÍịỊjJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrRsStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxXyYỳỲỷỶỹỸýÝỵỴzZ0123456789!"&\'()+,-./:;= '
	config['weights'] = 'weights/transformerocr.pth'
    # config['weights'] = '/home/v000354/Downloads/transformerocr_ben.pth'
	config['device'] = 'cpu'
	config['predictor']['beamsearch']=False
	device = config['device']
	detector = Predictor(config)
	print("Model recor loaded") 
    # load model yolo
	weights="weights/yolov4-tiny-custom_best.weights"
	config_yolo = "yolov4-tiny-custom.cfg"
	classes_yolo = "yolo.names"
	net = cv2.dnn.readNet(weights, config_yolo)
	print("Model yolo loaded") 
	with open(classes_yolo, 'r') as f:
		classes = [line.strip() for line in f.readlines()]

    #load model classify orientation
	model_orientation = load_model("weights/classify_orientation.h5")
	classes_orientation = ["rotate_0", "rotate_90", "rotate_180", "rotate_270"]
	# continually pool for new images to classify
	while True:
		# attempt to grab a batch of images from the database, then
		# initialize the image IDs and batch of images themselves
		queue = db.lrange(settings.IMAGE_QUEUE, 0,
			settings.BATCH_SIZE - 1)
		imageIDs = []
		batch = None

		# loop over the queue
		for q in queue:
			# deserialize the object and obtain the input image
			q = json.loads(q.decode("utf-8"))
			image = helpers.base64_decode_image(q["image"],
				settings.IMAGE_DTYPE,
				(1, 608, 608,
					settings.IMAGE_CHANS))

			# check to see if the batch list is None
			if batch is None:
				batch = image

			# otherwise, stack the data
			else:
				batch = np.vstack([batch, image])

			# update the list of image IDs
			imageIDs.append(q["id"])

		# check to see if we need to process the batch
		if len(imageIDs) > 0:
			# classify the batch
			print("* Batch size: {}".format(batch.shape))
			# preds = model.predict(batch)
			# print(image)
			results_info = pred_info(net, batch, classes, model_orientation, classes_orientation, detector)
			preds=[]
			for result in results_info:
				# print("DDDDDDDDD", result)
				preds.append(result)
			# results = imagenet_utils.decode_predictions(preds)

			# loop over the image IDs and their corresponding set of
			# results from our model
			for (imageID, resultSet) in zip(imageIDs, preds):
				# print("LLLLLL", resultSet)
				# initialize the list of output predictions
				# imencoded = cv2.imencode(".jpg", image)[1]
				# cv2.imwrite("namancut.jpg", resultSet)
				# img_b64 = base64.b64encode(resultSet).decode("utf-8")
				image_result, seller, address, timestamp, total_cost = resultSet
				imencoded = cv2.imencode(".jpg", image_result)[1]
				img_b64 = base64.b64encode(imencoded).decode("utf-8")
				output = {"image": img_b64, 'sellers':seller, 'addresses':address, 'timestamps':timestamp, 'total_costs':total_cost}
				# print(output)
				# loop over the results and add them to the list of
				# output predictions
				# for (imagenetID, label, prob) in resultSet:
				# 	r = {"label": label, "probability": float(prob)}
					# output.append(r)

				# store the output predictions in the database, using
				# the image ID as the key so we can fetch the results
				db.set(imageID, json.dumps(output))

			# remove the set of images from our queue
			db.ltrim(settings.IMAGE_QUEUE, len(imageIDs), -1)

		# sleep for a small amount
		time.sleep(settings.SERVER_SLEEP)

# if this is the main thread of execution start the model server
# process
if __name__ == "__main__":
	classify_process()