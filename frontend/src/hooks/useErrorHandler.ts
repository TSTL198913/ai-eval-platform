import { message } from 'antd';

interface ErrorHandlerOptions {
  logPrefix?: string;
  showMessage?: boolean;
}

/**
 * 错误处理Hook - 统一错误处理逻辑
 * 用于API调用、数据加载等场景
 */
export const useErrorHandler = (options: ErrorHandlerOptions = {}) => {
  const { logPrefix = 'Error', showMessage = true } = options;

  const handleError = (error: any, customMessage?: string) => {
    const errorMsg = customMessage || error?.message || '未知错误';

    console.error(`${logPrefix}:`, error);

    if (showMessage) {
      message.error(errorMsg);
    }

    return error;
  };

  return { handleError };
};
