import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])

train_dataset = datasets.MNIST(root='./__pycache__/', train=True, download=True, transform=transform)
test_dataset = datasets.MNIST(root='./__pycache__/', train=False, download=True, transform=transform)

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=1000, shuffle=False)

model = nn.Sequential(
    # 第一层：卷积 + 激活 + 池化
    nn.Conv2d(1, 6, kernel_size=5),      # 输入1通道，输出6通道，卷积核5x5
    nn.ReLU(),
    nn.MaxPool2d(kernel_size=2),         # 2x2 池化，图片缩小一半
    
    # 第二层：卷积 + 激活 + 池化
    nn.Conv2d(6, 16, kernel_size=5),     # 输入6通道，输出16通道
    nn.ReLU(),
    nn.MaxPool2d(kernel_size=2),         # 再缩小一半
    
    # 把 16*4*4 = 256 个点拉直（Flatten）
    nn.Flatten(),
    
    # 全连接层
    nn.Linear(16*4*4, 100),
    nn.ReLU(),
    nn.Linear(100, 84),
    nn.ReLU(),
    nn.Linear(84, 10)                    # 最终输出 10 个分类
)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

for epoch in range(10):
    for images, labels in train_loader:
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
    print(f"{epoch} loss {loss.item():.4f}")

# 6. 测试
correct = 0
with torch.no_grad():
    for images, labels in test_loader:
        outputs = model(images)
        pred = outputs.argmax(dim=1)
        correct += (pred == labels).sum().item()
print(f"测试集准确率: {correct / len(test_dataset) * 100:.2f}%")
