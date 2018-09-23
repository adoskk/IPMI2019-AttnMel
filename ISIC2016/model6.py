import torch
import torch.nn as nn
import torch.nn.functional as F
from blocks import ResNetBottleneckBlock, ResNetBottleneckBlock_CBAM
from initialize import *

'''
ResNet v1
CBAM - Convolutional Block Attention Module (ECCV 2018)
'''

class AttnResNet(nn.Module):
    def __init__(self, num_classes, attention=True, normalize_attn=True, init='kaimingNormal'):
        super(AttnResNet, self).__init__()
        self.pre_act = False
        self.attention = attention
        self.normalize_attn = normalize_attn
        n_blocks = [3, 4, 6, 3]
        features = [64, 256, 512, 1024, 2048]
        # conv block
        self.pre_conv = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=features[0], kernel_size=7, stride=2, padding=3, bias=False), # /2
            nn.BatchNorm2d(features[0]),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1) # /4
        )
        # res blocks
        if self.attention:
            self.layer1 = self._make_layer(ResNetBottleneckBlock_CBAM, in_features=features[0], out_features=features[1], num_blocks=n_blocks[0], stride=1, factor=4) # /4
            self.layer2 = self._make_layer(ResNetBottleneckBlock_CBAM, in_features=features[1], out_features=features[2], num_blocks=n_blocks[1], stride=2, factor=4) # /8
            self.layer3 = self._make_layer(ResNetBottleneckBlock_CBAM, in_features=features[2], out_features=features[3], num_blocks=n_blocks[2], stride=2, factor=4) # /16
            self.layer4 = self._make_layer(ResNetBottleneckBlock_CBAM, in_features=features[3], out_features=features[4], num_blocks=n_blocks[3], stride=2, factor=4) # /32
        else:
            self.layer1 = self._make_layer(ResNetBottleneckBlock, in_features=features[0], out_features=features[1], num_blocks=n_blocks[0], stride=1, factor=4) # /4
            self.layer2 = self._make_layer(ResNetBottleneckBlock, in_features=features[1], out_features=features[2], num_blocks=n_blocks[1], stride=2, factor=4) # /8
            self.layer3 = self._make_layer(ResNetBottleneckBlock, in_features=features[2], out_features=features[3], num_blocks=n_blocks[2], stride=2, factor=4) # /16
            self.layer4 = self._make_layer(ResNetBottleneckBlock, in_features=features[3], out_features=features[4], num_blocks=n_blocks[3], stride=2, factor=4) # /32
        self.feature = nn.AdaptiveAvgPool2d(output_size=(1,1)) # global average pooling
        # final classification layer
        self.classify = nn.Linear(in_features=features[4], out_features=num_classes, bias=True)
        # initialize
        if init == 'kaimingNormal':
            weights_init_kaimingNormal(self)
        elif init == 'kaimingUniform':
            weights_init_kaimingUniform(self)
        elif init == 'xavierNormal':
            weights_init_xavierNormal(self)
        elif init == 'xavierUniform':
            weights_init_xavierUniform(self)
        else:
            raise NotImplementedError("Invalid type of initialization!")
    def _make_layer(self, block, in_features, out_features, num_blocks, stride=1, factor=4):
        layers = []
        layers.append(block(in_features=in_features, out_features=out_features, pre_act=self.pre_act, stride=stride, factor=factor, normalize_attn=self.normalize_attn))
        for i in range(1, num_blocks):
            layers.append(block(in_features=out_features, out_features=out_features, pre_act=self.pre_act, stride=1, factor=factor, normalize_attn=self.normalize_attn))
        return nn.Sequential(*layers)
    def forward(self, x):
        pre = self.pre_conv(x)       # /4
        layer1 = self.layer1(pre)    # /4
        layer2 = self.layer2(layer1) # /8
        layer3 = self.layer3(layer2) # /16
        layer4 = self.layer4(layer3) # /32
        g = self.feature(layer4)     # /32 --> batch_sizex2048x1x1
        c1, c2, c3 = None, None, None
        out = self.classify(torch.squeeze(g))
        return [out, c1, c2, c3]