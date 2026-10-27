# Image repair

Repair corrupted JPEG, PNG, and BMP files. Pillow rebuilds a truncated scan first. If that fails, OpenCV decodes whatever blocks it can. A JPEG that still will not open can have its container cleaned, or its header replaced from a reference photo shot on the same camera at the same size.

One bad file does not stop the batch.

## Run on Ubuntu

Ubuntu 22.04 or 24.04 is enough. Python 3.10 or newer is required.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/iftikhar69/image-repair.git
cd image-repair
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python repair_web.py
```

Open http://127.0.0.1:8765. Leave that terminal running. Press Ctrl+C to stop.

Activate the environment again in every new terminal:

```bash
cd ~/image-repair
source .venv/bin/activate
```

If `python3 -m venv` says `ensurepip is not available`, install `python3-venv`, delete `.venv`, and create it again.

## Repair a folder from the command line

Put damaged files in `corrupted_images/`. Repaired files are written to `repaired_images/`. Files neither decoder could open are copied to `unrepairable_images/`.

```bash
python batch_repair.py
python batch_repair.py --workers 4
python batch_repair.py --reference camera_sample.jpg
```

`--reference` must be a JPEG that still opens, from the same camera and the same pixel size. It is used only when a file's header will not parse.

## Sample images

You do not need your own damaged photos to try the tool. After you clone, the files are in `samples/`:

| File | What is wrong |
| --- | --- |
| `samples/truncated.jpg` | The scan ends early, leaving a gray gap that repair fills in |
| `samples/dirty-container.jpg` | Extra bytes before and after the JPEG |
| `samples/broken-header.jpg` | The header was removed |
| `samples/reference.jpg` | A clean JPEG of the same scene, used to rebuild that header |
| `samples/mark.png` | A normal PNG |
| `samples/plate.bmp` | A normal bitmap |
| `samples/unreadable.jpg` | Text with a JPEG name. Repair should fail |

On the web page, choose **Repair sample images**. From the command line:

```bash
mkdir -p repaired_images unrepairable_images
python batch_repair.py --input samples --output repaired_images --failed unrepairable_images --reference samples/reference.jpg
```

Regenerate the files with `python scripts/make_samples.py`.

## Tests

```bash
python -m pytest
```

## Deploy on Render

`render.yaml` and `Procfile` are set. In Render, choose **New**, then **Blueprint**, and connect this repository. Render installs `requirements.txt` and starts:

```bash
gunicorn repair_web:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```
