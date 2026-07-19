function y = roundn(x, n)
    % MATLAB roundn兼容函数，仅用于显示跟踪速度
    y = round(x ./ (10 .^ n)) .* (10 .^ n);
end
