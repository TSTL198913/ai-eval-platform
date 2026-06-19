
import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Spin } from 'antd';
import { Lock, User, Eye, EyeOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../services/api';
import useAuthStore from '@/stores/authStore';

const { Title } = Typography;

const Login: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError('');
      const values = await form.validateFields();
      const response = await authApi.login({
        username: values.username,
        password: values.password,
      });
      login({ id: 1, username: values.username, email: '', role: 'user' }, response.access_token, response.refresh_token);
      navigate('/');
    } catch (err) {
      setError('登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 p-4'>
      <div className='absolute inset-0 overflow-hidden'>
        <div className='absolute -top-40 -right-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-pulse' />
        <div className='absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-pulse' style={{ animationDelay: '1s' }} />
      </div>
      
      <Card className='w-full max-w-md shadow-2xl bg-white/10 backdrop-blur-lg border-white/20' styles={{ body: { padding: '32px' } }}>
        <div className='text-center mb-8'>
          <div className='w-16 h-16 mx-auto mb-4 bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl flex items-center justify-center'>
            <Lock className='w-8 h-8 text-white' />
          </div>
          <Title level={2} className='text-white mb-2'>AI 评测平台</Title>
          <p className='text-white/60'>登录系统管理您的评估任务</p>
        </div>

        {error && <Alert message={error} type='error' showIcon className='mb-6' />}

        <Form form={form} onFinish={handleLogin} layout='vertical'>
          <Form.Item
            name='username'
            label={<span className='text-white'>用户名</span>}
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<User className='w-5 h-5 text-white/60' />}
              placeholder='请输入用户名'
              className='login-input bg-white/10 border-white/20 text-white placeholder-white/40'
              style={{ color: 'white' }}
            />
          </Form.Item>

          <Form.Item
            name='password'
            label={<span className='text-white'>密码</span>}
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<Lock className='w-5 h-5 text-white/60' />}
              placeholder='请输入密码'
              className='login-input bg-white/10 border-white/20 text-white placeholder-white/40'
              style={{ color: 'white' }}
              iconRender={(visible) => (visible ? <EyeOff className='w-5 h-5 text-white/60' /> : <Eye className='w-5 h-5 text-white/60' />)}
            />
          </Form.Item>

          <Form.Item className='flex items-center justify-between mb-6'>
            <label className='flex items-center text-white/60 cursor-pointer'>
              <input type='checkbox' className='mr-2' />
              <span>记住我</span>
            </label>
            <a href='#' className='text-blue-400 hover:text-blue-300'>忘记密码?</a>
          </Form.Item>

          <Form.Item>
            <Button type='primary' htmlType='submit' loading={loading} block size='large' className='h-12 bg-gradient-to-r from-blue-500 to-purple-500 border-0 hover:from-blue-600 hover:to-purple-600'>
              {loading ? <Spin size='small' /> : '登 录'}
            </Button>
          </Form.Item>
        </Form>

        <div className='text-center mt-6 text-white/40 text-sm'>
          <p>测试账号: admin / admin</p>
        </div>
      </Card>
    </div>
  );
};

export default Login;
