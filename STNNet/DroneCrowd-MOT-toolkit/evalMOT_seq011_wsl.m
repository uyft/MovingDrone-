clc;
clear all;
close all;
warning off all;

% ============================================================
% 获取当前工具包根目录，确保从任意目录启动都能正常运行
% ============================================================
toolkitRoot = fileparts(mfilename('fullpath'));
cd(toolkitRoot);

% ============================================================
% 添加官方工具包路径
% ============================================================
addpath(fullfile(toolkitRoot, 'display'));
addpath(fullfile(toolkitRoot, 'eval'));
addpath(genpath(fullfile(toolkitRoot, 'utils')));

% ============================================================
% 路径设置
% 只修改路径，不修改GOG算法、参数和评价方法
% ============================================================

% DroneCrowd-master/dataset
datasetPath = fullfile(toolkitRoot, '..', '..', 'dataset');

% 测试帧图片
seqPath = fullfile(datasetPath, 'test_data', 'images');

% STNNet/cyc_pts：模型逐帧定位结果
detPath = fullfile(toolkitRoot, '..', 'cyc_pts');

% STNNet/results/tracking/cyc_pts：GOG轨迹输出目录
resPath = fullfile(
    toolkitRoot,
    '..',
    'results',
    'tracking',
    'cyc_pts'
);

% 当前只评价序列011
listPath = fullfile(toolkitRoot, 'testlist_seq011.txt');

% 官方视频级标注
gtPath = fullfile(datasetPath, 'annotations');

% 不弹出逐帧显示窗口
isSeqDisplay = false;

% 使用官方GOG跟踪器
trackerName = 'GOG';

% ============================================================
% 打印路径，便于检查
% ============================================================
fprintf('============================================================\n');
fprintf('DroneCrowd 原始GOG跟踪与评测\n');
fprintf('工具包目录：%s\n', toolkitRoot);
fprintf('图片目录：%s\n', seqPath);
fprintf('定位结果：%s\n', detPath);
fprintf('跟踪输出：%s\n', resPath);
fprintf('序列列表：%s\n', listPath);
fprintf('真实标注：%s\n', gtPath);
fprintf('============================================================\n');

% ============================================================
% 检查必要文件
% ============================================================
if ~exist(seqPath, 'dir')
    error(['图片目录不存在：' seqPath]);
end

if ~exist(detPath, 'dir')
    error(['定位结果目录不存在：' detPath]);
end

if ~exist(gtPath, 'dir')
    error(['标注目录不存在：' gtPath]);
end

if ~exist(listPath, 'file')
    error(['序列列表不存在：' listPath]);
end

firstImage = fullfile(seqPath, 'img011001.jpg');
firstDetection = fullfile(detPath, 'img011001_loc.txt');
lastDetection = fullfile(detPath, 'img011300_loc.txt');
annotationFile = fullfile(gtPath, '00011.mat');

if ~exist(firstImage, 'file')
    error(['第一帧图片不存在：' firstImage]);
end

if ~exist(firstDetection, 'file')
    error(['第一帧预测不存在：' firstDetection]);
end

if ~exist(lastDetection, 'file')
    error(['第300帧预测不存在：' lastDetection]);
end

if ~exist(annotationFile, 'file')
    error(['标注文件不存在：' annotationFile]);
end

fprintf('\n路径与文件检查通过。\n');

% ============================================================
% 运行官方GOG跟踪器
% ============================================================
fprintf('\n开始运行原始GOG跟踪器……\n');

runTrackerAllClass(
    isSeqDisplay,
    seqPath,
    detPath,
    resPath,
    listPath,
    trackerName
);

% ============================================================
% 运行官方evaluateTrackA评测
% ============================================================
fprintf('\n开始运行官方轨迹评测……\n');

[ap, recall, precision] = evaluateTrackA(
    listPath,
    resPath,
    gtPath,
    trackerName
);

% ============================================================
% 显示结果
% evaluateTrackA的三个位置分别对应轨迹阈值：
% 0.10、0.15、0.20
% ============================================================
fprintf('\n============================================================\n');
fprintf('原始GOG轨迹评测完成\n');
fprintf('============================================================\n');

fprintf('\n轨迹重合阈值：\n');
disp([0.10, 0.15, 0.20]);

fprintf('AP：\n');
disp(ap);

fprintf('Recall：\n');
disp(recall);

fprintf('Precision：\n');
disp(precision);

% ============================================================
% 保存MAT格式指标
% ============================================================
if ~exist(resPath, 'dir')
    mkdir(resPath);
end

metricsPath = fullfile(resPath, 'metrics_seq011_GOG.mat');

save(
    metricsPath,
    'ap',
    'recall',
    'precision'
);

fprintf('指标文件：%s\n', metricsPath);
fprintf('轨迹文件：%s\n', ...
    fullfile(resPath, '00011_GOG.txt'));
fprintf('============================================================\n');
