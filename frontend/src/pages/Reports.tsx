import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Spin, Modal, Space, message, Tag } from 'antd';
import { FileText, Download, RefreshCw, Plus, Eye } from 'lucide-react';
import { reportApi } from '../services/api';
import { Report } from '../types';

const Reports: React.FC = () => {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const data = await reportApi.getReports();
      setReports(data.reports || []);
    } catch (err: any) {
      // 架构规范：报告列表加载失败必须抛出
      console.error('Failed to fetch reports:', err);
      message.error('获取报告列表失败');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    setGenerating(true);
    try {
      await reportApi.generateReport();
      message.success('报告生成成功');
      fetchReports();
    } catch (err: any) {
      // 架构规范：报告生成失败必须抛出让用户感知
      console.error('Failed to generate report:', err);
      message.error(`报告生成失败: ${err?.message || '未知错误'}`);
      throw err;
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (path: string) => {
    try {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = path.split('/').pop() || 'report.html';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success('下载成功');
    } catch (err: any) {
      // 架构规范：下载失败必须抛出
      console.error('Failed to download:', err);
      message.error(`下载失败: ${err?.message || '未知错误'}`);
      throw err;
    }
  };

  const handlePreview = (path: string) => {
    setPreviewUrl(path);
    setPreviewVisible(true);
  };

  const columns = [
    {
      title: '报告名称',
      dataIndex: 'filename',
      key: 'filename',
      render: (text: string) => <span className='font-medium text-blue-600'>{text}</span>,
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      render: (size: number) => {
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / (1024 * 1024)).toFixed(2)} MB`;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (timestamp: number) => {
        return new Date(timestamp).toLocaleString('zh-CN');
      },
    },
    {
      title: '状态',
      key: 'status',
      render: () => <Tag color='green'>已完成</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Report) => (
        <Space>
          <Button
            type='link'
            icon={<Eye />}
            onClick={() => handlePreview(record.path || '')}
          >
            预览
          </Button>
          <Button
            type='link'
            icon={<Download />}
            onClick={() => handleDownload(record.path || '')}
          >
            下载
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title='报告管理'
        extra={
          <Space>
            <Button
              icon={<RefreshCw />}
              onClick={fetchReports}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type='primary'
              icon={<Plus />}
              onClick={handleGenerateReport}
              loading={generating}
            >
              生成报告
            </Button>
          </Space>
        }
      >
        {loading ? (
          <div className='flex items-center justify-center h-64'>
            <Spin size='large' />
          </div>
        ) : reports.length === 0 ? (
          <div className='text-center py-12'>
            <FileText className='w-16 h-16 text-gray-300 mx-auto mb-4' />
            <p className='text-gray-400'>暂无报告</p>
            <p className='text-gray-300 text-sm mt-2'>点击上方按钮生成评测报告</p>
          </div>
        ) : (
          <Table
            columns={columns}
            dataSource={reports}
            rowKey='filename'
            pagination={{ pageSize: 10 }}
            scroll={{ x: 800 }}
          />
        )}
      </Card>

      <Modal
        title='报告预览'
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        width={900}
        footer={null}
      >
        {previewUrl && (
          <iframe
            src={previewUrl}
            style={{ width: '100%', height: '600px', border: 'none' }}
            title='Report Preview'
          />
        )}
      </Modal>
    </div>
  );
};

export default Reports
