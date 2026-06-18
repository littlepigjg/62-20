import React, { useEffect, useRef, useState } from 'react';
import {
  AutoComplete,
  Card,
  List,
  Tag,
  Space,
  Button,
  Input,
  Select,
  DatePicker,
  Modal,
  Empty,
  Tooltip,
  Collapse,
  Switch,
  Pagination,
  Typography,
  Divider,
  Popconfirm,
  Row,
  Col,
  App,
} from 'antd';
import {
  SearchOutlined,
  FilterOutlined,
  FireOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  StarOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { searchApi, serversApi } from '@/services/api';
import type {
  SearchResultItem,
  SearchSuggestion,
  SearchHistoryItem,
  SearchShortcut,
  SearchStats,
  ServerConfig,
} from '@/types';

const { RangePicker } = DatePicker;
const { Text, Title, Paragraph } = Typography;

const DOC_TYPE_OPTIONS = [
  { value: 'server', label: '服务器', color: 'blue' },
  { value: 'template', label: '脚本模板', color: 'purple' },
  { value: 'task', label: '执行任务', color: 'cyan' },
  { value: 'log', label: '日志', color: 'gold' },
];

const STATUS_OPTIONS = [
  { value: 'success', label: '成功', color: 'success' },
  { value: 'failed', label: '失败', color: 'warning' },
  { value: 'error', label: '错误', color: 'error' },
  { value: 'running', label: '执行中', color: 'processing' },
  { value: 'pending', label: '等待中', color: 'default' },
];

const docTypeMeta = (t: string) => DOC_TYPE_OPTIONS.find(o => o.value === t);
const statusMeta = (s: string) => STATUS_OPTIONS.find(o => o.value === s);

const parseHighlight = (text: string, keyBase: string) => {
  const parts = text.split(/\[\[HIGHLIGHT\]\](.*?)\[\[\/HIGHLIGHT\]\]/s);
  return parts.map((part, i) =>
    i % 2 === 1 ? <mark key={`${keyBase}-${i}`}>{part}</mark> : <span key={`${keyBase}-${i}`}>{part}</span>,
  );
};

const formatTime = (ts: string | null | undefined): string => {
  if (!ts) return '-';
  const d = dayjs(ts);
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : String(ts);
};

const GlobalSearch: React.FC = () => {
  const { message } = App.useApp();
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [popular, setPopular] = useState<SearchSuggestion[]>([]);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const [docTypes, setDocTypes] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [serverIds, setServerIds] = useState<string[]>([]);
  const [serverTags, setServerTags] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [fuzzy, setFuzzy] = useState(true);
  const [expandSynonyms, setExpandSynonyms] = useState(true);
  const [recordHistory, setRecordHistory] = useState(true);

  const [servers, setServers] = useState<ServerConfig[]>([]);
  const [allServerTags, setAllServerTags] = useState<string[]>([]);
  const [stats, setStats] = useState<SearchStats | null>(null);
  const [shortcuts, setShortcuts] = useState<SearchShortcut[]>([]);
  const [reindexing, setReindexing] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const [shortcutModalOpen, setShortcutModalOpen] = useState(false);
  const [shortcutName, setShortcutName] = useState('');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const buildFilters = () => ({
    doc_types: docTypes.length ? docTypes : undefined,
    statuses: statuses.length ? statuses : undefined,
    server_ids: serverIds.length ? serverIds : undefined,
    server_tags: serverTags.length ? serverTags : undefined,
    tags: tags.length ? tags : undefined,
    start_time: timeRange ? timeRange[0].format('YYYY-MM-DDTHH:mm:ss') : undefined,
    end_time: timeRange ? timeRange[1].format('YYYY-MM-DDTHH:mm:ss') : undefined,
  });

  const buildFiltersForShortcut = () => {
    const f = buildFilters();
    return Object.fromEntries(Object.entries(f).filter(([, v]) => v !== undefined));
  };

  const executeSearch = async (q: string, pageNum: number) => {
    setLoading(true);
    try {
      const res = await searchApi.search({
        query: q,
        ...buildFilters(),
        limit: pageSize,
        offset: (pageNum - 1) * pageSize,
        fuzzy,
        expand_synonyms: expandSynonyms,
        record_history: recordHistory,
      });
      setResults(res.results);
      setTotal(res.total);
      setSearched(true);
      setPage(pageNum);
      fetchHistory();
    } catch (e: any) {
      message.error('搜索失败: ' + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const h = await searchApi.history(8);
      setHistory(h);
    } catch {
      /* noop */
    }
  };

  const fetchShortcuts = async () => {
    try {
      const sc = await searchApi.listShortcuts();
      setShortcuts(sc);
    } catch {
      /* noop */
    }
  };

  const fetchStats = async () => {
    try {
      const s = await searchApi.stats();
      setStats(s);
    } catch {
      /* noop */
    }
  };

  useEffect(() => {
    const init = async () => {
      try {
        const [p, h, s, st, sv, sc] = await Promise.all([
          searchApi.popular(8),
          searchApi.history(8),
          searchApi.stats(),
          serversApi.tags(),
          serversApi.list(),
          searchApi.listShortcuts(),
        ]);
        setPopular(p);
        setHistory(h);
        setStats(s);
        setAllServerTags(st);
        setServers(sv);
        setShortcuts(sc);
      } catch {
        message.error('加载搜索数据失败');
      }
    };
    init();
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const s = await searchApi.suggestions(query, 8);
        setSuggestions(s);
      } catch {
        /* noop */
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const res = await searchApi.reindex();
      message.success(`索引重建完成，共 ${res.total_docs} 个文档`);
      await fetchStats();
    } catch (e: any) {
      message.error('重建索引失败: ' + (e.response?.data?.detail || e.message));
    } finally {
      setReindexing(false);
    }
  };

  const executeShortcut = async (sc: SearchShortcut) => {
    setLoading(true);
    try {
      const res = await searchApi.executeShortcut(sc.id, pageSize, 0);
      setQuery(sc.query);
      setResults(res.results);
      setTotal(res.total);
      setSearched(true);
      setPage(1);
      message.success(`已执行快捷方式「${sc.name}」`);
      fetchShortcuts();
    } catch (e: any) {
      message.error('执行快捷方式失败: ' + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  const openShortcutModal = () => {
    if (!query.trim() && !docTypes.length && !statuses.length && !serverIds.length && !serverTags.length && !tags.length && !timeRange) {
      message.warning('请先输入搜索词或设置筛选条件');
      return;
    }
    setShortcutName('');
    setShortcutModalOpen(true);
  };

  const saveShortcut = async () => {
    if (!shortcutName.trim()) {
      message.warning('请输入快捷方式名称');
      return;
    }
    try {
      await searchApi.createShortcut({
        name: shortcutName.trim(),
        query,
        filters: buildFiltersForShortcut(),
      });
      message.success('快捷方式已保存');
      setShortcutModalOpen(false);
      fetchShortcuts();
    } catch (e: any) {
      message.error('保存失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const deleteShortcut = async (id: string) => {
    try {
      await searchApi.deleteShortcut(id);
      message.success('快捷方式已删除');
      fetchShortcuts();
    } catch (e: any) {
      message.error('删除失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const resetFilters = () => {
    setDocTypes([]);
    setStatuses([]);
    setServerIds([]);
    setServerTags([]);
    setTags([]);
    setTimeRange(null);
    setFuzzy(true);
    setExpandSynonyms(true);
  };

  const autoOptions: any[] = [];
  if (suggestions.length) {
    autoOptions.push({
      label: <Text type="secondary" style={{ fontSize: 12 }}><SearchOutlined /> 实时建议</Text>,
      options: suggestions.map(s => ({
        value: s.text,
        label: (
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{s.text}</Text>
            <Space size={4}>
              {s.type === 'fuzzy' && <Tag color="orange" style={{ margin: 0, fontSize: 11 }}>模糊</Tag>}
              {s.count !== undefined && <Text type="secondary" style={{ fontSize: 11 }}>{s.count}</Text>}
            </Space>
          </Space>
        ),
      })),
    });
  }
  if (popular.length) {
    autoOptions.push({
      label: <Text type="secondary" style={{ fontSize: 12 }}><FireOutlined /> 热门搜索</Text>,
      options: popular.map(s => ({
        value: s.text,
        label: (
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{s.text}</Text>
            {s.count !== undefined && <Text type="secondary" style={{ fontSize: 11 }}>{s.count} 次</Text>}
          </Space>
        ),
      })),
    });
  }
  if (history.length) {
    autoOptions.push({
      label: <Text type="secondary" style={{ fontSize: 12 }}><ClockCircleOutlined /> 历史搜索</Text>,
      options: history.map(h => ({
        value: h.query,
        label: (
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{h.query}</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>{formatTime(h.timestamp)}</Text>
          </Space>
        ),
      })),
    });
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <SearchOutlined style={{ marginRight: 8 }} />
            全局搜索
          </Title>
          <Paragraph style={{ margin: '4px 0 0 0', color: '#888' }}>
            跨服务器、脚本、任务、日志的统一检索
          </Paragraph>
        </div>
        <Space direction="vertical" align="end" size={4}>
          {stats && (
            <Space size={4} wrap>
              <Tag icon={<DatabaseOutlined />} color="blue">索引 {stats.total_docs}</Tag>
              {!stats.initialized && <Tag color="orange">未初始化</Tag>}
              {Object.entries(stats.by_type).map(([k, v]) => {
                const meta = docTypeMeta(k);
                return (
                  <Tag key={k} color={meta?.color} style={{ fontSize: 11 }}>
                    {meta?.label || k} {v}
                  </Tag>
                );
              })}
            </Space>
          )}
          <Button icon={<ReloadOutlined />} onClick={handleReindex} loading={reindexing}>
            重建索引
          </Button>
        </Space>
      </div>

      <Card className="global-search-card">
        <AutoComplete
          value={query}
          onChange={(val: string) => setQuery(val)}
          onSelect={(val: string) => {
            setQuery(val);
            executeSearch(val, 1);
          }}
          options={autoOptions}
          style={{ width: '100%' }}
          filterOption={false}
          defaultActiveFirstOption={false}
          popupMatchSelectWidth
        >
          <Input.Search
            placeholder="输入关键词搜索服务器 / 脚本 / 任务 / 日志（支持模糊匹配与同义词扩展）"
            enterButton="搜索"
            size="large"
            allowClear
            onSearch={(val: string) => executeSearch(val, 1)}
          />
        </AutoComplete>

        <Collapse
          style={{ marginTop: 16 }}
          items={[{
            key: 'filters',
            label: (
              <Space>
                <FilterOutlined />
                <span>高级筛选</span>
                {(docTypes.length + statuses.length + serverIds.length + serverTags.length + tags.length) > 0 && (
                  <Tag color="blue" style={{ margin: 0 }}>
                    {(docTypes.length + statuses.length + serverIds.length + serverTags.length + tags.length) + (timeRange ? 1 : 0)} 项
                  </Tag>
                )}
              </Space>
            ),
            children: (
              <div>
                <Row gutter={[16, 12]}>
                  <Col xs={24} sm={12} lg={6}>
                    <Text type="secondary" style={{ fontSize: 12 }}>文档类型</Text>
                    <Select
                      mode="multiple"
                      placeholder="全部类型"
                      value={docTypes}
                      onChange={setDocTypes}
                      style={{ width: '100%', marginTop: 4 }}
                      allowClear
                      maxTagCount="responsive"
                    >
                      {DOC_TYPE_OPTIONS.map(o => (
                        <Select.Option key={o.value} value={o.value}>{o.label}</Select.Option>
                      ))}
                    </Select>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Text type="secondary" style={{ fontSize: 12 }}>执行状态</Text>
                    <Select
                      mode="multiple"
                      placeholder="全部状态"
                      value={statuses}
                      onChange={setStatuses}
                      style={{ width: '100%', marginTop: 4 }}
                      allowClear
                      maxTagCount="responsive"
                    >
                      {STATUS_OPTIONS.map(o => (
                        <Select.Option key={o.value} value={o.value}>{o.label}</Select.Option>
                      ))}
                    </Select>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Text type="secondary" style={{ fontSize: 12 }}>服务器</Text>
                    <Select
                      mode="multiple"
                      placeholder="选择服务器"
                      value={serverIds}
                      onChange={setServerIds}
                      style={{ width: '100%', marginTop: 4 }}
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      maxTagCount="responsive"
                    >
                      {servers.map(s => (
                        <Select.Option key={s.id} value={s.id} label={s.name}>
                          {s.name} ({s.host})
                        </Select.Option>
                      ))}
                    </Select>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Text type="secondary" style={{ fontSize: 12 }}>服务器标签</Text>
                    <Select
                      mode="multiple"
                      placeholder="选择标签"
                      value={serverTags}
                      onChange={setServerTags}
                      style={{ width: '100%', marginTop: 4 }}
                      allowClear
                      maxTagCount="responsive"
                    >
                      {allServerTags.map(t => (
                        <Select.Option key={t} value={t}>{t}</Select.Option>
                      ))}
                    </Select>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Text type="secondary" style={{ fontSize: 12 }}>标签</Text>
                    <Select
                      mode="tags"
                      placeholder="输入标签后回车"
                      value={tags}
                      onChange={setTags}
                      style={{ width: '100%', marginTop: 4 }}
                      allowClear
                      tokenSeparators={[',', ' ']}
                    />
                  </Col>
                  <Col xs={24} sm={12} lg={12}>
                    <Text type="secondary" style={{ fontSize: 12 }}>时间范围</Text>
                    <RangePicker
                      showTime
                      value={timeRange}
                      onChange={(dates) => setTimeRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
                      style={{ width: '100%', marginTop: 4 }}
                      placeholder={['开始时间', '结束时间']}
                    />
                  </Col>
                </Row>
                <Divider style={{ margin: '12px 0' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                  <Space wrap>
                    <Space size={4}>
                      <Switch size="small" checked={fuzzy} onChange={setFuzzy} />
                      <Text style={{ fontSize: 12 }}>模糊匹配</Text>
                    </Space>
                    <Space size={4}>
                      <Switch size="small" checked={expandSynonyms} onChange={setExpandSynonyms} />
                      <Text style={{ fontSize: 12 }}>同义词扩展</Text>
                    </Space>
                    <Space size={4}>
                      <Switch size="small" checked={recordHistory} onChange={setRecordHistory} />
                      <Text style={{ fontSize: 12 }}>记录历史</Text>
                    </Space>
                  </Space>
                  <Space>
                    <Button size="small" onClick={resetFilters}>重置筛选</Button>
                    <Button type="primary" size="small" icon={<SearchOutlined />} onClick={() => executeSearch(query, 1)} loading={loading}>
                      搜索
                    </Button>
                  </Space>
                </div>
              </div>
            ),
          }]}
        />
      </Card>

      <Card
        title={
          <Space>
            <span>搜索结果</span>
            {searched && <Tag color="blue">{total} 条</Tag>}
          </Space>
        }
        loading={loading}
      >
        {!searched ? (
          <Empty description="输入关键词或设置筛选条件后开始搜索" />
        ) : results.length === 0 ? (
          <Empty description="没有找到匹配的结果" />
        ) : (
          <>
            <List
              dataSource={results}
              renderItem={(item: SearchResultItem) => {
                const dMeta = docTypeMeta(item.doc_type);
                const sMeta = item.status ? statusMeta(item.status) : undefined;
                const server = servers.find(s => s.id === item.server_id);
                return (
                  <List.Item style={{ borderBottom: '1px solid #f0f0f0', padding: '12px 0' }}>
                    <div className="global-search-result" style={{ width: '100%' }}>
                      <Space direction="vertical" size={6} style={{ width: '100%' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                          <Space size={6} wrap>
                            <Tag color={dMeta?.color || 'default'}>{dMeta?.label || item.doc_type}</Tag>
                            {item.status && (
                              <Tag color={sMeta?.color || 'default'}>{sMeta?.label || item.status}</Tag>
                            )}
                            {item.server_id && (
                              <Tooltip title={item.server_id}>
                                <Tag style={{ margin: 0 }}>
                                  {server?.name || item.server_id}
                                </Tag>
                              </Tooltip>
                            )}
                            {item.server_tags.map(t => (
                              <Tag key={t} color="geekblue" style={{ fontSize: 11 }}>{t}</Tag>
                            ))}
                          </Space>
                          <Tooltip title="相关性评分">
                            <Tag color="gold" style={{ margin: 0, fontFamily: 'monospace' }}>
                              {item.score.toFixed(2)}
                            </Tag>
                          </Tooltip>
                        </div>
                        <Text strong style={{ fontSize: 14 }}>{item.title}</Text>
                        {item.matched_terms.length > 0 && (
                          <Space size={4} wrap>
                            {item.matched_terms.map(t => (
                              <Tag key={t} color="blue" style={{ fontSize: 11, margin: 0 }}>{t}</Tag>
                            ))}
                          </Space>
                        )}
                        {item.highlights.length > 0 && (
                          <div className="global-search-highlight">
                            {item.highlights.slice(0, 3).map((h, i) => (
                              <div key={i} className="global-search-snippet">
                                {parseHighlight(h, String(i))}
                              </div>
                            ))}
                          </div>
                        )}
                        <Space size={12} style={{ fontSize: 11, color: '#999' }}>
                          <span><ClockCircleOutlined /> {formatTime(item.timestamp)}</span>
                          {item.tags.length > 0 && <span>标签：{item.tags.join(', ')}</span>}
                        </Space>
                      </Space>
                    </div>
                  </List.Item>
                );
              }}
              locale={{ emptyText: <Empty description="没有找到匹配的结果" /> }}
            />
            {total > pageSize && (
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                onChange={(p) => executeSearch(query, p)}
                showTotal={(t) => `共 ${t} 条结果`}
                style={{ marginTop: 16, textAlign: 'right' }}
              />
            )}
          </>
        )}
      </Card>

      <Card
        title={
          <Space>
            <StarOutlined />
            <span>搜索快捷方式</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openShortcutModal}>
            保存当前搜索
          </Button>
        }
      >
        {shortcuts.length === 0 ? (
          <Empty description="还没有保存的快捷方式" />
        ) : (
          <List
            dataSource={shortcuts}
            renderItem={(sc: SearchShortcut) => (
              <List.Item
                actions={[
                  <Button
                    key="run"
                    type="primary"
                    size="small"
                    icon={<ThunderboltOutlined />}
                    onClick={() => executeShortcut(sc)}
                  >
                    执行
                  </Button>,
                  <Popconfirm
                    key="del"
                    title="删除此快捷方式？"
                    onConfirm={() => deleteShortcut(sc.id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{sc.name}</Text>
                      <Tag color="blue">{sc.usage_count} 次</Tag>
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Text code style={{ fontSize: 12 }}>{sc.query || '(空关键词)'}</Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        更新于 {formatTime(sc.updated_at)}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      <Modal
        title="保存搜索快捷方式"
        open={shortcutModalOpen}
        onOk={saveShortcut}
        onCancel={() => setShortcutModalOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>快捷方式名称</Text>
            <Input
              placeholder="例如：重启类操作"
              value={shortcutName}
              onChange={e => setShortcutName(e.target.value)}
              style={{ marginTop: 4 }}
              onPressEnter={saveShortcut}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>搜索词</Text>
            <div style={{ marginTop: 4 }}>
              <Text code>{query || '(空)'}</Text>
            </div>
          </div>
        </Space>
      </Modal>
    </Space>
  );
};

export default GlobalSearch;
