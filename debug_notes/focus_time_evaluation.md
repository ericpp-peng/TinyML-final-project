# Focus Time Evaluation Notes

## Baseline: conservative Lab 4 recognizer settings

- Date: 2026-06-06 18:19 PDT
- Firmware: `focus_time` model with Lab 4-style streaming inference
- Recognizer settings:
  - average window: 1000 ms
  - detection threshold: 200
  - suppression: 1500 ms
  - minimum count: 3
- Responder threshold: 200
- Test method: user repeatedly said "focus time" during a 90-second serial monitor window.
- Spoken trigger attempts: 40
- Serial `FOCUS_TIME` detections: 15
- Baseline recall: 15 / 40 = 37.5%
- Observed detection scores: approximately 0.792 to 0.831

## Interpretation

The baseline firmware has good precision in informal live testing: unrelated speech did not trigger `FOCUS_TIME`. The main issue is recall. Since the model can produce high `focus_time` scores, the most likely bottleneck is the post-processing stage: averaging window, detection threshold, and suppression duration.

## Next Experiment: sensitivity tuning

Change only the command recognition post-processing:

- Reduce averaging window so short true-positive peaks are not diluted.
- Reduce detection threshold slightly.
- Reduce suppression so repeated test utterances are not artificially ignored.
- Reduce minimum count from 3 to 2 so detections can happen sooner.

This keeps the model and feature extraction fixed, making the comparison easier to interpret.

## Attempted v2: aggressive sensitivity tuning

- Recognizer settings:
  - average window: 500 ms
  - detection threshold: 175
  - suppression: 900 ms
  - minimum count: 2
- Responder threshold: 175
- Result: rejected.
- Reason: a 20-second negative speech check produced 2 false `FOCUS_TIME` detections while the user was speaking normally without saying "focus time".

This showed that reducing both the averaging window and threshold is too aggressive. It improves sensitivity, but harms the project's most important property: avoiding false positives.

## v2a: conservative suppression tuning

- Recognizer settings:
  - average window: 1000 ms
  - detection threshold: 200
  - suppression: 900 ms
  - minimum count: 3
- Responder threshold: 200

This version keeps the conservative score behavior from the baseline, but shortens the suppression period from 1500 ms to 900 ms. The goal is to avoid missing repeated true triggers during testing while preserving the low false-positive behavior observed in the baseline.

### v2a result

- Negative speech check: 0 false positives in 20 seconds while the user was speaking normally without saying "focus time"
- Spoken trigger attempts: 40
- Serial `FOCUS_TIME` detections: 11
- Recall: 11 / 40 = 27.5%
- Result: rejected.

This result was worse than the baseline, so suppression duration is probably not the main bottleneck. The more likely issue is sliding-window alignment: the model was trained on complete 2-second clips, but live inference often sees the phrase at different positions inside the rolling window.

## v3: time-shifted retraining

The next experiment retrains the same `focus_time` model with time-shift augmentation. The goal is to teach the model that `focus time` is still positive even when it appears earlier or later within the 2-second input window.

### v3 result: 700 ms time shift

- Training time shift: 700 ms
- Offline check on 30 recorded `focus_time` clips: 30 / 30 correct
- Negative speech check: 2 false `FOCUS_TIME` detections in 20 seconds while the user was speaking normally without saying "focus time"
- Result: rejected.

The 700 ms time shift made the model too permissive. It likely improved alignment tolerance, but it also reduced the separation between silence/noise and the trigger phrase.

## v4: moderate time-shifted retraining

The next experiment uses a smaller time shift of 300 ms. This is stronger than the original 100 ms augmentation, but less aggressive than 700 ms. The goal is to improve alignment robustness while preserving the low false-positive behavior of the baseline.

### v4 result: 300 ms time shift

- Training time shift: 300 ms
- Negative speech check: 2 false `FOCUS_TIME` detections in 20 seconds while the user was speaking normally without saying "focus time"
- Result: rejected.

Even moderate time-shift augmentation increased false positives during normal speech. The best current firmware is still the baseline model because it preserves the desired low false-positive behavior.

## Current best version

- Model: baseline `focus_time` model
- Recognizer: Lab 4 default settings
- Responder threshold: 200
- Baseline recall: 37.5%
- Negative speech behavior: best observed precision so far

## Next recommended improvement

The next step should not be more threshold relaxation or stronger time shifting. Those approaches were tested and caused false positives. The most likely improvement is collecting hard negative examples from the actual deployment environment:

- normal conversation while working
- English phrases that contain "focus" or "time" but are not the trigger
- nearby words such as "work time", "phone time", "time to work", "focus", and "timer"
- Chinese speech and casual filler speech

Then retrain with both:

- the original `focus_time` positives
- the new hard negatives as `unknown`
- modest time shift only if negative speech precision remains good

This should improve recall while preserving the project's most important behavior: no false positives during unrelated speech.

## v5: event-based raw peak detector

This experiment tested the hypothesis that the model may be correct, but the decision timing is poor. The firmware kept the baseline model, removed the Lab 4 averaged recognizer decision, and instead treated speech as an event:

- start listening when non-silence speech is detected
- track the maximum raw `focus_time` score during the event
- print one `FOCUS_TIME` event if the peak score exceeds the threshold

### v5 result

- Model: baseline `focus_time`
- Decision method: raw peak score inside a speech event
- Negative speech check: 7 false `FOCUS_TIME` detections in 30 seconds while the user was speaking normally without saying "focus time"
- Result: rejected.

This showed that the raw model score can spike high during unrelated speech. The Lab 4 averaging logic was suppressing many of those spikes, which explains why the baseline has much better precision. Therefore, a better timing strategy is still promising, but it should not rely only on raw peak score. It needs either:

- hard negative training data so unrelated speech produces lower raw `focus_time` scores, or
- a true phrase-aligned 2-second capture followed by one complete-clip inference, or
- a two-stage detector that confirms the phrase before logging.
