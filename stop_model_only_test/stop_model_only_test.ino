#include <TensorFlowLite.h>
#include "micro_features_model.h"
#include "tensorflow/lite/micro/micro_error_reporter.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/version.h"

namespace {
tflite::MicroErrorReporter micro_error_reporter;
tflite::ErrorReporter* error_reporter = &micro_error_reporter;
const tflite::Model* model = nullptr;
constexpr int kTensorArenaSize = 60 * 1024;
uint8_t tensor_arena[kTensorArenaSize];
bool setup_ok = false;
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  const unsigned long start = millis();
  while (!Serial && millis() - start < 2000) {
    digitalWrite(LED_BUILTIN, (millis() / 100) & 1);
  }
  Serial.println("MODEL_ONLY starting");

  model = tflite::GetModel(g_model);
  Serial.print("schema=");
  Serial.println(model->version());
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    Serial.println("MODEL_ONLY schema error");
    return;
  }

  static tflite::MicroMutableOpResolver<5> resolver(error_reporter);
  resolver.AddDepthwiseConv2D();
  resolver.AddFullyConnected();
  resolver.AddSoftmax();
  resolver.AddReshape();
  resolver.AddConv2D();

  static tflite::MicroInterpreter interpreter(
      model, resolver, tensor_arena, kTensorArenaSize, error_reporter);
  TfLiteStatus status = interpreter.AllocateTensors();
  Serial.print("AllocateTensors status=");
  Serial.println(status == kTfLiteOk ? "OK" : "ERROR");
  if (status != kTfLiteOk) {
    return;
  }

  TfLiteTensor* input = interpreter.input(0);
  TfLiteTensor* output = interpreter.output(0);
  Serial.print("input bytes=");
  Serial.println(input->bytes);
  Serial.print("output bytes=");
  Serial.println(output->bytes);
  Serial.println("MODEL_ONLY SETUP_OK");
  setup_ok = true;
}

void loop() {
  static unsigned long last = 0;
  if (millis() - last >= 1000) {
    last = millis();
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    Serial.print(setup_ok ? "MODEL_HEARTBEAT," : "MODEL_SETUP_FAILED,");
    Serial.println(millis());
  }
}
