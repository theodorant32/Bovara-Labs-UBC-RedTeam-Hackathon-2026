# Required Data Files

This repository does not include large model and dataset files. To run the full system, you'll need to add these files:

## Required Files

### 1. Trained Model (Required for Classification)
- **File:** `signal_classifier.keras`
- **Location:** `FindMyForce-API/models/`
- **Size:** ~50-100 MB
- **Purpose:** CNN model for RF signal classification

### 2. Training Data (Required for Training/Retraining)
- **File:** `training_data.hdf5`
- **Location:** `FindMyForce-API/dataset/`
- **Size:** ~50-100 MB
- **Purpose:** Labeled IQ samples for model training

### 3. Synthetic Hostile Data (Optional)
- **File:** `synthetic_hostile.hdf5`
- **Location:** `FindMyForce-API/dataset/`
- **Purpose:** Additional hostile emitter samples

## Where to Get These Files

If you participated in the hackathon, these files were provided during the event. Contact the organizers or check your hackathon materials.

For development without the official data:
1. **Generate synthetic data:** Run `python test/generate_synthetic.py` in `FindMyForce-API/`
2. **Use demo mode:** The frontend will run with mock data when no backend is connected

## Git LFS (Recommended for Future)

If you plan to version these files, consider using Git LFS:

```bash
git lfs install
git lfs track "*.keras"
git lfs track "*.hdf5"
git add .gitattributes
git add models/ dataset/
```

## Running Without Data Files

The application will still function in **demo mode** with:
- Mock track data displayed on the map
- Simulated signal classifications
- Full UI functionality

To enable live classification, connect to the API backend with the model file present.
