import torch
from torchvision import models, transforms
from PIL import Image
import numpy as np
from typing import List

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

image_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])

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

def predict_tile(image_array: np.ndarray, model: torch.nn.Module) -> float:
    pil_image = Image.fromarray(image_array.astype(np.uint8))
    tensor = image_transform(pil_image).unsqueeze(0).to(device)

    model.eval()
    with torch.no_grad():
        output = model(tensor)
        prob = torch.sigmoid(output).item()

    return round(prob, 2)

def predict_tile_batch(image_arrays: List[np.ndarray], model: torch.nn.Module) -> List[float]:
    tensors = []

    for img in image_arrays:
        pil = Image.fromarray(img.astype(np.uint8))
        tensor = image_transform(pil)
        tensors.append(tensor)

    batch_tensor = torch.stack(tensors).to(device)

    model.eval()
    with torch.no_grad():
        output = model(batch_tensor)
        probs = torch.sigmoid(output).squeeze().cpu().numpy()

    return [round(float(p), 2) for p in probs]
