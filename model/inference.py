import torch
from torchvision import models, transforms
from PIL import Image
import numpy as np

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Define transform (same as training)
image_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])

# Load the model
def load_model():
    model = models.resnet18(pretrained=False)
    model.fc = torch.nn.Sequential(
        torch.nn.Dropout(0.4),
        torch.nn.Linear(model.fc.in_features, 1)
    )
    model.load_state_dict(torch.load("model/resnet18_terrabite_global.pth", map_location=device))
    model.eval()
    model.to(device)
    return model

model = load_model()

# Run inference on an RGB image array
def predict_tile(image_array: np.ndarray) -> float:
    pil_image = Image.fromarray(image_array.astype(np.uint8))
    tensor = image_transform(pil_image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(tensor)
        prob = torch.sigmoid(output).item()

    return round(prob, 3)
