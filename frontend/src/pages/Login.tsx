import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Spin, Checkbox } from 'antd';
import { Lock, User, Zap, Eye, EyeOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../services/api';
import useAuthStore from '@/stores/authStore';

const { Title } = Typography;

const Login: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState<'weak' | 'medium' | 'strong' | null>(null);
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);

  useEffect(() => {
    const savedUsername = localStorage.getItem('remember_username');
    if (savedUsername) {
      form.setFieldsValue({ username: savedUsername });
      setRememberMe(true);
    }
  }, [form]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !loading) {
        handleLogin();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [loading]);

  const checkPasswordStrength = (password: string) => {
    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[a-z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score <= 2) return 'weak';
    if (score <= 4) return 'medium';
    return 'strong';
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setPasswordStrength(value ? checkPasswordStrength(value) : null);
  };

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError('');
      const values = await form.validateFields();

      if (rememberMe) {
        localStorage.setItem('remember_username', values.username);
      } else {
        localStorage.removeItem('remember_username');
      }

      const response = await authApi.login({
        username: values.username,
        password: values.password,
      });
      login({ id: 1, username: values.username, email: '', role: 'user', created_at: '' }, response.access_token, response.refresh_token);
      navigate('/');
    } catch (err) {
      setError('登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  const getPasswordStrengthConfig = () => {
    switch (passwordStrength) {
      case 'weak':
        return { label: '弱', color: 'bg-red-500' };
      case 'medium':
        return { label: '中', color: 'bg-yellow-500' };
      case 'strong':
        return { label: '强', color: 'bg-green-500' };
      default:
        return null;
    }
  };

  const strengthConfig = getPasswordStrengthConfig();

  return (
    <div className='min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900 p-4'>
      <div className='absolute inset-0 overflow-hidden'>
        <div className='absolute top-1/4 -right-32 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl' />
        <div className='absolute bottom-1/4 -left-32 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl' />
        <div className='absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-3xl' />
      </div>

      <Card
        className='w-full max-w-md shadow-2xl bg-white/8 backdrop-blur-xl border-white/10'
        styles={{ body: { padding: '40px' } }}
      >
        <div className='text-center mb-8'>
          <div className='w-20 h-20 mx-auto mb-5 bg-gradient-to-r from-blue-500 via-purple-500 to-indigo-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/25'>
            <Lock className='w-10 h-10 text-white' />
          </div>
          <Title level={2} className='text-slate-800 mb-2 text-2xl font-bold'>AI 评测平台</Title>
          <p className='text-slate-500 text-sm'>登录系统管理您的评估任务</p>
        </div>

        {error && <Alert message={error} type='error' showIcon className='mb-6' />}

        <Form
          form={form}
          onFinish={handleLogin}
          layout='vertical'
          autoComplete='off'
        >
          <Form.Item
            name='username'
            label={<span className='text-slate-700 font-medium'>用户名</span>}
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' }
            ]}
            className='mb-5'
          >
            <Input
              prefix={<User className='w-5 h-5 text-slate-400' />}
              placeholder='请输入用户名'
              className='h-12 rounded-xl border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all'
              size='large'
              autoFocus
            />
          </Form.Item>

          <Form.Item
            name='password'
            label={<span className='text-slate-700 font-medium'>密码</span>}
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' }
            ]}
            className='mb-4'
          >
            <Input
              type={passwordVisible ? 'text' : 'password'}
              placeholder='请输入密码'
              size='large'
              onChange={handlePasswordChange}
              suffix={
                <button
                  type='button'
                  onClick={() => setPasswordVisible(!passwordVisible)}
                  className='p-1 hover:bg-slate-100 rounded transition-colors'
                >
                  {passwordVisible ? (
                    <EyeOff className='w-5 h-5 text-slate-400' />
                  ) : (
                    <Eye className='w-5 h-5 text-slate-400' />
                  )}
                </button>
              }
              className='h-12 [&>input]:h-12'
            />
          </Form.Item>

          {passwordStrength && (
            <div className='mb-5 flex items-center gap-2'>
              <span className='text-xs text-slate-500'>密码强度:</span>
              <div className='flex-1 flex gap-1'>
                <div className={`h-1.5 flex-1 rounded-full ${passwordStrength === 'weak' ? 'bg-red-500' : passwordStrength === 'medium' || passwordStrength === 'strong' ? 'bg-yellow-500' : 'bg-slate-200'}`} />
                <div className={`h-1.5 flex-1 rounded-full ${passwordStrength === 'medium' ? 'bg-yellow-500' : passwordStrength === 'strong' ? 'bg-green-500' : 'bg-slate-200'}`} />
                <div className={`h-1.5 flex-1 rounded-full ${passwordStrength === 'strong' ? 'bg-green-500' : 'bg-slate-200'}`} />
              </div>
              <span className={`text-xs font-medium ${passwordStrength === 'weak' ? 'text-red-500' : passwordStrength === 'medium' ? 'text-yellow-500' : 'text-green-500'}`}>
                {strengthConfig?.label}
              </span>
            </div>
          )}

          <div className='flex items-center justify-between mb-6'>
            <Checkbox
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className='text-slate-600'
            >
              记住我
            </Checkbox>
            <a href='#' className='text-blue-600 hover:text-blue-700 text-sm font-medium'>忘记密码?</a>
          </div>

          <Form.Item className='mb-6'>
            <Button
              type='primary'
              htmlType='submit'
              loading={loading}
              block
              size='large'
              className='h-14 rounded-xl bg-gradient-to-r from-blue-600 via-purple-600 to-indigo-600 border-0 hover:from-blue-700 hover:via-purple-700 hover:to-indigo-700 text-white font-semibold text-base shadow-lg shadow-blue-500/25 transition-all hover:shadow-xl'
            >
              {loading ? (
                <Spin size='small' className='mr-2' />
              ) : (
                <>
                  <Zap className='w-5 h-5 mr-2 inline-block' />
                  登录
                </>
              )}
            </Button>
          </Form.Item>
        </Form>

        <div className='relative'>
          <div className='absolute inset-0 flex items-center'>
            <div className='w-full border-t border-slate-200' />
          </div>
          <div className='relative flex justify-center text-sm'>
            <span className='px-4 bg-white/8 text-slate-400'>测试账号</span>
          </div>
        </div>

        <div className='mt-4 text-center'>
          <div className='inline-flex items-center gap-2 px-4 py-2 bg-slate-50 rounded-lg border border-slate-100'>
            <User className='w-4 h-4 text-slate-400' />
            <span className='text-slate-600 font-mono'>admin</span>
            <span className='text-slate-300'>/</span>
            <Lock className='w-4 h-4 text-slate-400' />
            <span className='text-slate-600 font-mono'>admin123</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Login;
