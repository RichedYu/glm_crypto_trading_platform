import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Card,
  Row,
  Col,
  Statistic,
  Progress,
  Tag,
  Table,
  Alert,
  Divider,
  Tooltip,
  Badge,
  Space,
  Button,
  message,
} from "antd";
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  SyncOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  SafetyOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  DashboardOutlined,
  LineChartOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { optionsApi } from "../../services/optionsApi";
import { useMarketData } from "../../hooks/useMarketData";
import type {
  PQSpreadData,
  PortfolioGreeks,
  OptionPosition,
  HedgeStatus,
} from "../../services/optionsApi";

// WebSocket 事件类型定义
interface PortfolioRiskWS {
  total_delta: number;
  total_gamma: number;
  total_vega: number;
  total_theta: number;
  total_rho: number;
  leverage?: number;
  position_ratio?: number;
}

interface MacroStateWS {
  macro_regime?: string;
  regime_score?: number;
  fomo_score?: number;
  sentiment_score?: number;
}

// 风险等级颜色映射
const getRiskLevelColor = (value: number, thresholds: [number, number]) => {
  if (Math.abs(value) < thresholds[0]) return "#52c41a"; // 绿色 - 安全
  if (Math.abs(value) < thresholds[1]) return "#faad14"; // 黄色 - 警告
  return "#ff4d4f"; // 红色 - 危险
};

// 格式化百分比
const formatPercent = (value: number, precision = 2) => {
  return `${(value * 100).toFixed(precision)}%`;
};

// 格式化数字
const formatNumber = (value: number, precision = 4) => {
  return value.toFixed(precision);
};

const OptionsPanel: React.FC = () => {
  // API 数据状态
  const [pqSpread, setPQSpread] = useState<PQSpreadData | null>(null);
  const [greeks, setGreeks] = useState<PortfolioGreeks | null>(null);
  const [positions, setPositions] = useState<OptionPosition[]>([]);
  const [hedgeStatus, setHedgeStatus] = useState<HedgeStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // WebSocket 实时数据
  const wsRiskData = useMarketData<PortfolioRiskWS>("portfolio.risk");
  const wsMacroData = useMarketData<MacroStateWS>("market.macro");
  const wsPing = useMarketData<{ type: string }>("ping");
  const wsConnected = wsPing !== undefined;

  // 合并 API 数据和 WebSocket 实时数据
  const riskOverview = useMemo(() => {
    if (wsRiskData) {
      return wsRiskData;
    }
    if (greeks) {
      return {
        total_delta: greeks.total_delta,
        total_gamma: greeks.total_gamma,
        total_vega: greeks.total_vega,
        total_theta: greeks.total_theta,
        total_rho: greeks.total_rho,
      };
    }
    return null;
  }, [wsRiskData, greeks]);

  // 合并宏观数据
  const macroState = useMemo(() => {
    if (wsMacroData) {
      return wsMacroData;
    }
    if (pqSpread) {
      return {
        macro_regime: pqSpread.macro_regime,
        regime_score: pqSpread.regime_score,
        fomo_score: pqSpread.fomo_score,
      };
    }
    return null;
  }, [wsMacroData, pqSpread]);

  // 数据获取函数（带错误处理和降级）
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const results = await Promise.allSettled([
      optionsApi.getPQSpread("BTC/USDT"),
      optionsApi.getPortfolioGreeks(),
      optionsApi.getOptionPositions(),
      optionsApi.getHedgeStatus(),
    ]);

    // 处理 P-Q 价差
    if (results[0].status === "fulfilled") {
      setPQSpread(results[0].value);
    } else {
      console.error("Failed to fetch PQ spread:", results[0].reason);
    }

    // 处理 Greeks
    if (results[1].status === "fulfilled") {
      setGreeks(results[1].value);
    } else {
      console.error("Failed to fetch Greeks:", results[1].reason);
    }

    // 处理持仓
    if (results[2].status === "fulfilled") {
      setPositions(results[2].value.positions || []);
    } else {
      console.error("Failed to fetch positions:", results[2].reason);
    }

    // 处理对冲状态
    if (results[3].status === "fulfilled") {
      setHedgeStatus(results[3].value);
    } else {
      console.error("Failed to fetch hedge status:", results[3].reason);
    }

    // 检查是否全部失败
    const allFailed = results.every((r) => r.status === "rejected");
    if (allFailed) {
      setError("无法连接到服务器，请检查网络连接");
      message.error("数据加载失败，请稍后重试");
    }

    setLastUpdate(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    // 降低轮询频率，因为有 WebSocket 实时推送
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // 信号颜色
  const getSignalColor = (signal: string) => {
    if (signal === "buy_volatility") return "success";
    if (signal === "sell_volatility") return "error";
    return "default";
  };

  // 对冲状态颜色
  const getHedgeStatusColor = (
    status: string
  ): "success" | "warning" | "error" => {
    if (status === "well_hedged") return "success";
    if (status === "acceptable") return "warning";
    return "error";
  };

  // 意图类型图标
  const getIntentIcon = (intentType?: string) => {
    switch (intentType) {
      case "increase_long_gamma":
        return <ArrowUpOutlined style={{ color: "#52c41a" }} />;
      case "increase_short_gamma":
        return <ArrowDownOutlined style={{ color: "#ff4d4f" }} />;
      case "hold":
        return <SafetyOutlined style={{ color: "#1890ff" }} />;
      default:
        return <DashboardOutlined />;
    }
  };

  // 宏观周期颜色
  const getMacroRegimeColor = (regime?: string) => {
    switch (regime) {
      case "bull":
        return "green";
      case "bear":
        return "red";
      case "panic":
        return "volcano";
      default:
        return "default";
    }
  };

  // FOMO 风险等级
  const getFomoRiskLevel = (score?: number) => {
    if (!score) return { level: "未知", color: "default" };
    if (score < 0.3) return { level: "低", color: "green" };
    if (score < 0.6) return { level: "中", color: "orange" };
    return { level: "高", color: "red" };
  };

  // 表格列定义
  const positionColumns: ColumnsType<OptionPosition> = [
    {
      title: "合约",
      dataIndex: "symbol",
      key: "symbol",
      fixed: "left",
      width: 180,
      render: (text: string) => {
        const isCall = text.includes("-C");
        return (
          <Space>
            <span style={{ fontFamily: "monospace", fontWeight: 500 }}>
              {text}
            </span>
            <Tag color={isCall ? "cyan" : "magenta"} style={{ margin: 0 }}>
              {isCall ? "CALL" : "PUT"}
            </Tag>
          </Space>
        );
      },
    },
    {
      title: "数量",
      dataIndex: "quantity",
      key: "quantity",
      width: 100,
      align: "right",
      render: (val: number) => (
        <span style={{ fontFamily: "monospace" }}>{formatNumber(val)}</span>
      ),
    },
    {
      title: "均价",
      dataIndex: "avg_price",
      key: "avg_price",
      width: 100,
      align: "right",
      render: (val: number) => (
        <span style={{ fontFamily: "monospace" }}>${val.toFixed(2)}</span>
      ),
    },
    {
      title: "Delta",
      key: "delta",
      width: 90,
      align: "right",
      render: (_, record) => (
        <span
          style={{
            fontFamily: "monospace",
            color: getRiskLevelColor(record.greeks?.delta || 0, [0.3, 0.6]),
          }}
        >
          {record.greeks?.delta?.toFixed(4) || "-"}
        </span>
      ),
    },
    {
      title: "Gamma",
      key: "gamma",
      width: 90,
      align: "right",
      render: (_, record) => (
        <span style={{ fontFamily: "monospace" }}>
          {record.greeks?.gamma?.toFixed(4) || "-"}
        </span>
      ),
    },
    {
      title: "Vega",
      key: "vega",
      width: 90,
      align: "right",
      render: (_, record) => (
        <span style={{ fontFamily: "monospace" }}>
          {record.greeks?.vega?.toFixed(4) || "-"}
        </span>
      ),
    },
    {
      title: "未实现盈亏",
      dataIndex: "unrealized_pnl",
      key: "unrealized_pnl",
      width: 120,
      align: "right",
      render: (val: number) => (
        <span
          style={{
            fontFamily: "monospace",
            fontWeight: 600,
            color: val >= 0 ? "#52c41a" : "#ff4d4f",
          }}
        >
          {val >= 0 ? "+" : ""}${val.toFixed(2)}
        </span>
      ),
    },
  ];

  // 错误状态显示
  if (error && !pqSpread && !greeks) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <Alert
          message="数据加载失败"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={fetchData} icon={<ReloadOutlined />}>
              重试
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      {/* 页面标题 */}
      <div
        style={{
          marginBottom: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>
            <ThunderboltOutlined style={{ marginRight: 8, color: "#1890ff" }} />
            Gamma Scalping 控制台
          </h1>
          <p style={{ margin: "4px 0 0", color: "#8c8c8c" }}>
            实时监控 P vs Q 波动率套利策略
          </p>
        </div>
        <Space>
          <Tooltip
            title={wsConnected ? "WebSocket 已连接" : "WebSocket 未连接"}
          >
            <Badge status={wsConnected ? "success" : "error"} />
            <WifiOutlined
              style={{
                color: wsConnected ? "#52c41a" : "#ff4d4f",
                marginLeft: 4,
              }}
            />
          </Tooltip>
          {lastUpdate && (
            <span style={{ color: "#8c8c8c", fontSize: 12 }}>
              更新于 {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <Button
            icon={<ReloadOutlined spin={loading} />}
            onClick={fetchData}
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      </div>

      {/* 第一行：组合风险总览 + Delta 对冲状态 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <DashboardOutlined />
                <span>组合风险总览</span>
                {wsRiskData && (
                  <Tag color="green" style={{ marginLeft: 8 }}>
                    <SyncOutlined spin /> 实时
                  </Tag>
                )}
              </Space>
            }
            loading={loading && !riskOverview}
            bordered={false}
            style={{ boxShadow: "0 1px 2px rgba(0,0,0,0.03)" }}
          >
            {riskOverview && (
              <Row gutter={[16, 16]}>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title={
                      <Tooltip title="组合总 Delta 敞口">
                        <span>Delta</span>
                      </Tooltip>
                    }
                    value={riskOverview.total_delta}
                    precision={4}
                    valueStyle={{
                      color: getRiskLevelColor(
                        riskOverview.total_delta,
                        [0.05, 0.1]
                      ),
                      fontFamily: "monospace",
                    }}
                    prefix={
                      riskOverview.total_delta > 0 ? (
                        <ArrowUpOutlined />
                      ) : riskOverview.total_delta < 0 ? (
                        <ArrowDownOutlined />
                      ) : null
                    }
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title={
                      <Tooltip title="Gamma 敞口 - 价格变动敏感度">
                        <span>Gamma</span>
                      </Tooltip>
                    }
                    value={riskOverview.total_gamma}
                    precision={4}
                    valueStyle={{ fontFamily: "monospace", color: "#1890ff" }}
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title={
                      <Tooltip title="Vega 敞口 - 波动率敏感度">
                        <span>Vega</span>
                      </Tooltip>
                    }
                    value={riskOverview.total_vega}
                    precision={4}
                    valueStyle={{ fontFamily: "monospace", color: "#722ed1" }}
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title={
                      <Tooltip title="Theta 敞口 - 时间衰减">
                        <span>Theta</span>
                      </Tooltip>
                    }
                    value={riskOverview.total_theta}
                    precision={4}
                    valueStyle={{
                      fontFamily: "monospace",
                      color:
                        riskOverview.total_theta < 0 ? "#ff4d4f" : "#52c41a",
                    }}
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title={
                      <Tooltip title="Rho 敞口 - 利率敏感度">
                        <span>Rho</span>
                      </Tooltip>
                    }
                    value={riskOverview.total_rho}
                    precision={4}
                    valueStyle={{ fontFamily: "monospace" }}
                  />
                </Col>
                {riskOverview.leverage && (
                  <Col xs={12} sm={8} md={4}>
                    <Statistic
                      title={
                        <Tooltip title="组合杠杆率">
                          <span>杠杆</span>
                        </Tooltip>
                      }
                      value={riskOverview.leverage}
                      precision={2}
                      suffix="x"
                      valueStyle={{
                        fontFamily: "monospace",
                        color: getRiskLevelColor(riskOverview.leverage, [2, 5]),
                      }}
                    />
                  </Col>
                )}
              </Row>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <SafetyOutlined />
                <span>Delta 对冲状态</span>
              </Space>
            }
            loading={loading && !hedgeStatus}
            bordered={false}
            style={{ boxShadow: "0 1px 2px rgba(0,0,0,0.03)", height: "100%" }}
          >
            {hedgeStatus && (
              <>
                <Alert
                  message={
                    <Space>
                      {hedgeStatus.status === "well_hedged" ? (
                        <CheckCircleOutlined />
                      ) : hedgeStatus.status === "acceptable" ? (
                        <ExclamationCircleOutlined />
                      ) : (
                        <WarningOutlined />
                      )}
                      <span>
                        {hedgeStatus.status === "well_hedged"
                          ? "对冲良好"
                          : hedgeStatus.status === "acceptable"
                          ? "可接受范围"
                          : "需要对冲"}
                      </span>
                    </Space>
                  }
                  description={
                    <span style={{ fontSize: 12 }}>
                      建议:{" "}
                      {hedgeStatus.recommended_action === "none"
                        ? "无需操作"
                        : hedgeStatus.recommended_action}
                    </span>
                  }
                  type={getHedgeStatusColor(hedgeStatus.status)}
                  showIcon={false}
                  style={{ marginBottom: 12 }}
                />
                <div style={{ textAlign: "center" }}>
                  <Statistic
                    value={hedgeStatus.total_delta}
                    precision={4}
                    valueStyle={{
                      fontSize: 28,
                      fontFamily: "monospace",
                      color: getRiskLevelColor(
                        hedgeStatus.total_delta,
                        [0.02, 0.05]
                      ),
                    }}
                    prefix={hedgeStatus.total_delta > 0 ? "+" : ""}
                  />
                  <Progress
                    percent={Math.min(
                      Math.abs(hedgeStatus.total_delta) * 1000,
                      100
                    )}
                    status={
                      Math.abs(hedgeStatus.total_delta) < 0.05
                        ? "success"
                        : "exception"
                    }
                    strokeColor={{
                      "0%": "#52c41a",
                      "50%": "#faad14",
                      "100%": "#ff4d4f",
                    }}
                    showInfo={false}
                    style={{ marginTop: 8 }}
                  />
                </div>
              </>
            )}
          </Card>
        </Col>
      </Row>

      {/* 第二行：P vs Q 控制台 */}
      <Card
        title={
          <Space>
            <LineChartOutlined />
            <span>P vs Q 波动率套利控制台</span>
          </Space>
        }
        style={{ marginBottom: 16, boxShadow: "0 1px 2px rgba(0,0,0,0.03)" }}
        loading={loading && !pqSpread}
        bordered={false}
      >
        {pqSpread && (
          <>
            <Row gutter={[24, 16]}>
              {/* P 波动率 */}
              <Col xs={24} sm={12} md={6}>
                <div
                  style={{
                    background:
                      "linear-gradient(135deg, #1890ff15 0%, #1890ff05 100%)",
                    borderRadius: 8,
                    padding: 16,
                    border: "1px solid #1890ff30",
                  }}
                >
                  <div
                    style={{ color: "#8c8c8c", marginBottom: 4, fontSize: 12 }}
                  >
                    P (市场隐含波动率)
                  </div>
                  <div
                    style={{
                      fontSize: 32,
                      fontWeight: 600,
                      fontFamily: "monospace",
                      color: "#1890ff",
                    }}
                  >
                    {formatPercent(pqSpread.p_vol)}
                  </div>
                </div>
              </Col>

              {/* Q 波动率 */}
              <Col xs={24} sm={12} md={6}>
                <div
                  style={{
                    background:
                      "linear-gradient(135deg, #52c41a15 0%, #52c41a05 100%)",
                    borderRadius: 8,
                    padding: 16,
                    border: "1px solid #52c41a30",
                  }}
                >
                  <div
                    style={{ color: "#8c8c8c", marginBottom: 4, fontSize: 12 }}
                  >
                    Q (模型预测波动率)
                  </div>
                  <div
                    style={{
                      fontSize: 32,
                      fontWeight: 600,
                      fontFamily: "monospace",
                      color: "#52c41a",
                    }}
                  >
                    {formatPercent(pqSpread.q_vol)}
                  </div>
                </div>
              </Col>

              {/* P-Q 价差 */}
              <Col xs={24} sm={12} md={6}>
                <div
                  style={{
                    background:
                      pqSpread.spread > 0
                        ? "linear-gradient(135deg, #52c41a15 0%, #52c41a05 100%)"
                        : "linear-gradient(135deg, #ff4d4f15 0%, #ff4d4f05 100%)",
                    borderRadius: 8,
                    padding: 16,
                    border: `1px solid ${
                      pqSpread.spread > 0 ? "#52c41a30" : "#ff4d4f30"
                    }`,
                  }}
                >
                  <div
                    style={{ color: "#8c8c8c", marginBottom: 4, fontSize: 12 }}
                  >
                    P-Q 价差
                  </div>
                  <div
                    style={{
                      fontSize: 32,
                      fontWeight: 600,
                      fontFamily: "monospace",
                      color: pqSpread.spread > 0 ? "#52c41a" : "#ff4d4f",
                    }}
                  >
                    {pqSpread.spread > 0 ? "+" : ""}
                    {formatPercent(pqSpread.spread)}
                  </div>
                </div>
              </Col>

              {/* 交易信号 */}
              <Col xs={24} sm={12} md={6}>
                <div
                  style={{
                    background: "#fafafa",
                    borderRadius: 8,
                    padding: 16,
                    border: "1px solid #d9d9d9",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{ color: "#8c8c8c", marginBottom: 8, fontSize: 12 }}
                  >
                    交易信号
                  </div>
                  <Tag
                    color={getSignalColor(pqSpread.signal)}
                    style={{ fontSize: 16, padding: "4px 16px", margin: 0 }}
                  >
                    {pqSpread.signal === "buy_volatility"
                      ? "📈 做多波动率"
                      : "📉 做空波动率"}
                  </Tag>
                  <div style={{ marginTop: 8 }}>
                    <Progress
                      percent={pqSpread.confidence * 100}
                      size="small"
                      format={(p) => `${p?.toFixed(0)}%`}
                      strokeColor={
                        pqSpread.confidence > 0.7 ? "#52c41a" : "#faad14"
                      }
                    />
                    <span style={{ fontSize: 11, color: "#8c8c8c" }}>
                      置信度
                    </span>
                  </div>
                </div>
              </Col>
            </Row>

            <Divider style={{ margin: "16px 0" }} />

            {/* 策略意图 + 宏观状态 */}
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card
                  size="small"
                  title={
                    <Space>
                      {getIntentIcon(pqSpread.intent_type)}
                      <span>策略意图</span>
                    </Space>
                  }
                  bordered
                  style={{ background: "#fafafa" }}
                >
                  <div style={{ fontSize: 16, fontWeight: 500 }}>
                    {pqSpread.intent_type === "increase_long_gamma"
                      ? "增加 Long Gamma 敞口"
                      : pqSpread.intent_type === "increase_short_gamma"
                      ? "增加 Short Gamma 敞口"
                      : pqSpread.intent_type === "hold"
                      ? "保持观望"
                      : pqSpread.intent_type || "未知"}
                  </div>
                  <div style={{ color: "#8c8c8c", marginTop: 4, fontSize: 13 }}>
                    {pqSpread.intent_reason === "market_underpricing_volatility"
                      ? "市场低估波动率"
                      : pqSpread.intent_reason ===
                        "market_overpricing_volatility"
                      ? "市场高估波动率"
                      : pqSpread.intent_reason === "high_fomo_risk"
                      ? "FOMO 风险过高，暂停交易"
                      : pqSpread.intent_reason || "暂无原因"}
                  </div>
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card
                  size="small"
                  title={
                    <Space>
                      <ThunderboltOutlined />
                      <span>宏观 / FOMO 状态</span>
                      {wsMacroData && (
                        <Tag color="green" style={{ marginLeft: 4 }}>
                          <SyncOutlined spin /> 实时
                        </Tag>
                      )}
                    </Space>
                  }
                  bordered
                  style={{ background: "#fafafa" }}
                >
                  <Row gutter={16}>
                    <Col span={8}>
                      <div style={{ color: "#8c8c8c", fontSize: 12 }}>
                        宏观周期
                      </div>
                      <Tag
                        color={getMacroRegimeColor(macroState?.macro_regime)}
                        style={{ marginTop: 4 }}
                      >
                        {macroState?.macro_regime === "bull"
                          ? "🐂 牛市"
                          : macroState?.macro_regime === "bear"
                          ? "🐻 熊市"
                          : macroState?.macro_regime === "panic"
                          ? "😱 恐慌"
                          : "❓ 未知"}
                      </Tag>
                    </Col>
                    <Col span={8}>
                      <div style={{ color: "#8c8c8c", fontSize: 12 }}>
                        周期强度
                      </div>
                      <div
                        style={{
                          fontFamily: "monospace",
                          fontWeight: 500,
                          marginTop: 4,
                        }}
                      >
                        {(macroState?.regime_score ?? 0).toFixed(2)}
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ color: "#8c8c8c", fontSize: 12 }}>
                        FOMO 指标
                      </div>
                      <Tag
                        color={getFomoRiskLevel(macroState?.fomo_score).color}
                        style={{ marginTop: 4 }}
                      >
                        {(macroState?.fomo_score ?? 0).toFixed(2)} (
                        {getFomoRiskLevel(macroState?.fomo_score).level})
                      </Tag>
                    </Col>
                  </Row>
                </Card>
              </Col>
            </Row>
          </>
        )}
      </Card>

      {/* 第三行：Greeks 细节 + 期权持仓 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <DashboardOutlined />
                <span>Greeks 细节</span>
              </Space>
            }
            loading={loading && !greeks}
            bordered={false}
            style={{ boxShadow: "0 1px 2px rgba(0,0,0,0.03)", height: "100%" }}
          >
            {greeks && (
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Statistic
                    title="Delta"
                    value={greeks.total_delta}
                    precision={4}
                    valueStyle={{
                      fontFamily: "monospace",
                      color: getRiskLevelColor(greeks.total_delta, [0.05, 0.1]),
                    }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Gamma"
                    value={greeks.total_gamma}
                    precision={4}
                    valueStyle={{ fontFamily: "monospace", color: "#1890ff" }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Vega"
                    value={greeks.total_vega}
                    precision={4}
                    valueStyle={{ fontFamily: "monospace", color: "#722ed1" }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Theta"
                    value={greeks.total_theta}
                    precision={4}
                    valueStyle={{
                      fontFamily: "monospace",
                      color: greeks.total_theta < 0 ? "#ff4d4f" : "#52c41a",
                    }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Rho"
                    value={greeks.total_rho}
                    precision={4}
                    valueStyle={{ fontFamily: "monospace" }}
                  />
                </Col>
                <Col span={12}>
                  <div style={{ marginTop: 8 }}>
                    <Tag
                      color={
                        greeks.hedge_status === "neutral"
                          ? "success"
                          : "warning"
                      }
                      icon={
                        <SyncOutlined
                          spin={greeks.hedge_status !== "neutral"}
                        />
                      }
                      style={{ fontSize: 14, padding: "4px 12px" }}
                    >
                      {greeks.hedge_status === "neutral"
                        ? "Delta 中性"
                        : "需要对冲"}
                    </Tag>
                  </div>
                </Col>
              </Row>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <LineChartOutlined />
                <span>期权持仓明细</span>
                <Tag color="blue">{positions.length} 个持仓</Tag>
              </Space>
            }
            loading={loading && positions.length === 0}
            bordered={false}
            style={{ boxShadow: "0 1px 2px rgba(0,0,0,0.03)" }}
          >
            <Table
              columns={positionColumns}
              dataSource={positions}
              rowKey="symbol"
              pagination={{ pageSize: 8, size: "small" }}
              size="small"
              scroll={{ x: 800 }}
              locale={{ emptyText: "暂无期权持仓" }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default OptionsPanel;
