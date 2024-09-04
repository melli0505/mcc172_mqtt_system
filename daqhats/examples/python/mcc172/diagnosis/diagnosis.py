import os
import tensorflow.lite as tf
from statistics import mode
from csv import reader
import numpy as np

def load_model(path):
	print("Now load Model...")
	model_file = path

	with open(model_file, "rb") as fid:
		tflite_model = fid.read()

	inter = tf.Interpreter(model_content=tflite_model)
	inter.allocate_tensors()

	input_details = inter.get_input_details()
	output_details = inter.get_output_details()

	return inter, input_details, output_details


def diagnosis(data, inter, input_details, output_details, shape):
	y_pred = []
	for d in data:
		inter.set_tensor(input_details[0]['index'], d.reshape(1, shape))
		inter.invoke()
		output_data = inter.get_tensor(output_details[0]['index'])
		y_pred.append(output_data.argmax())

	return mode(y_pred)

def preprocessing(data, shape, scaler):#path):
	# filename = sorted(os.listdir(path))[-1]
	# data = []
	# file = reader(open(path + filename, "r"), delimiter=",")
	# for row in file:
	# 	data.extend(row)
	data = np.array(data[:102400], dtype=np.float32).reshape(-1, 1)
	
	data = scaler.transform(np.array(data).reshape(102400, 1))
	data = np.array(data, dtype=np.float32).reshape(len(data)// shape, shape)
	return data



# data_file = input("Enter data path\n -")
# shape = int(input("Enter model input shape\n -"))
# inter, input_details, output_details = load_model()
# data = preprocessing(data_file)
# print(data.shape)
# result = diagnosis(data, inter, input_details, output_details, shape)

# category = ["normal", "misalignment", "unbalance", "damaged bearing"]

# print(f"\n-----------------------------------------\nDiagnosis Result : {category[result]} \n-----------------------------------------")
