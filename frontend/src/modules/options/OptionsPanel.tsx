import React, { useState, useEffect } from "react";
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
} from "antd";
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { optionsApi } from "../../services/optionsApi";
import type {
  PQSpreadData,
  PortfolioGreeks,
  OptionPosition,
  HedgeStatus,
} from "../../services/optionsApi";

interface RiskOverview {
  total_delta: number;
  total_gamma: number;
  total_vega: number;
  total_theta: number;
  total_rho: number;
  leverage?: number;
  position_ratio?: number;
}

const OptionsPanel: React.FC = () => {
  const [pqSpread, setPQSpread] = useState<PQSpreadData | null>(null);
  const [greeks, setGreeks] = useState<PortfolioGreeks | null>(null);
  const [positions, setPositions] = useState<OptionPosition[]>([]);
  const [hedgeStatus, setHedgeStatus] = useState<HedgeStatus | null>(null);
  const [riskOverview, setRiskOverview] = useState<RiskOverview | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // 每5秒更新
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      // 获取P-Q价差
      const pqData = await optionsApi.getPQSpread("BTC/USDT");
      setPQSpread(pqData);

      // 获取Greeks
      const greeksData = await optionsApi.getPortfolioGreeks();
      setGreeks(greeksData);

      // 从 risk metrics 中推导组合风险概览（如果后端扩展了字段则自动展示）
      setRiskOverview({
        total_delta: greeksData.total_delta,
        total_gamma: greeksData.total_gamma,
        total_vega: greeksData.total_vega,
        total_theta: greeksData.total_theta,
        total_rho: greeksData.total_rho,
      });

      // 获取期权持仓
      const posData = await optionsApi.getOptionPositions();
      setPositions(posData.positions || []);

      // 获取对冲状态
      const hedgeData = await optionsApi.getHedgeStatus();
      setHedgeStatus(hedgeData);
    } catch (error) {
      console.error("Failed to fetch options data:", error);
    } finally {
      setLoading(false);
    }
  };

  const getSignalColor = (signal: string) => {
    if (signal === "buy_volatility") return "green";
    if (signal === "sell_volatility") return "red";
    return "default";
  };

  const getHedgeStatusColor = (status: string) => {
    if (status === "well_hedged") return "success";
    if (status === "acceptable") return "warning";
    return "error";
  };

  const positionColumns: ColumnsType<OptionPosition> = [
    {
      title: "合约",
      dataIndex: "symbol",
      key: "symbol",
      render: (text: string) => {
        const isCall = text.includes("-C");
        return (
          <span>
            {text}{" "}
            <Tag color={isCall ? "green" : "red"}>
              {isCall ? "Call" : "Put"}
            </Tag>
          </span>
        );
      },
    },
    {
      title: "数量",
      dataIndex: "quantity",
      key: "quantity",
      render: (val: number) => val.toFixed(4),
    },
    {
      title: "均价",
      dataIndex: "avg_price",
      key: "avg_price",
      render: (val: number) => `$${val.toFixed(2)}`,
    },
    {
      title: "Delta",
      key: "delta",
      render: (_, record) => record.greeks?.delta?.toFixed(4) || "-",
    },
    {
      title: "Gamma",
      key: "gamma",
      render: (_, record) => record.greeks?.gamma?.toFixed(4) || "-",
    },
    {
      title: "Vega",
      key: "vega",
      render: (_, record) => record.greeks?.vega?.toFixed(4) || "-",
    },
    {
      title: "未实现盈亏",
      dataIndex: "unrealized_pnl",
      key: "unrealized_pnl",
      render: (val: number) => (
        <span style={{ color: val >= 0 ? "#3f8600" : "#cf1322" }}>
          ${val.toFixed(2)}
        </span>
      ),
    },
  ];

  return (
    <div style={{ padding: "24px" }}>
      <h2>Gamma Scalping 风险看板</h2>
      <Divider style={{ marginTop: 8, marginBottom: 24 }}>
        Portfolio & Gamma Overview
      </Divider>

      {/* 第一行：组合风险总览 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={16}>
          <Card
            title="组合风险总览 (Portfolio Risk Overview)"
            loading={loading}
          >
            {riskOverview && (
              <Row gutter={16}>
                <Col span={4}>
                  <Statistic
                    title="Delta (总敞口)"
                    value={riskOverview.total_delta}
                    precision={4}
                  />
                </Col>
                <Col span={4}>
                  <Statistic
                    title="Gamma"
                    value={riskOverview.total_gamma}
                    precision={4}
                  />
                </Col>
                <Col span={4}>
                  <Statistic
                    title="Vega"
                    value={riskOverview.total_vega}
                    precision={4}
                  />
                </Col>
                <Col span={4}>
                  <Statistic
                    title="Theta"
                    value={riskOverview.total_theta}
                    precision={4}
                  />
                </Col>
                <Col span={4}>
                  <Statistic
                    title="Rho"
                    value={riskOverview.total_rho}
                    precision={4}
                  />
                </Col>
              </Row>
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Delta 对冲状态" loading={loading}>
            {hedgeStatus && (
              <>
                <Alert
                  message={`对冲状态: ${hedgeStatus.status}`}
                  description={`建议操作: ${hedgeStatus.recommended_action}`}
                  type={getHedgeStatusColor(hedgeStatus.status)}
                  showIcon
                  style={{ marginBottom: 8 }}
                />
                <Statistic
                  title="总Delta敞口"
                  value={hedgeStatus.total_delta}
                  precision={4}
                  prefix={
                    hedgeStatus.total_delta > 0 ? (
                      <ArrowUpOutlined />
                    ) : (
                      <ArrowDownOutlined />
                    )
                  }
                  valueStyle={{
                    color:
                      Math.abs(hedgeStatus.total_delta) < 0.05
                        ? "#3f8600"
                        : "#cf1322",
                  }}
                />
                <Progress
                  percent={Math.min(
                    Math.abs(hedgeStatus.total_delta) * 100,
                    100
                  )}
                  status={
                    Math.abs(hedgeStatus.total_delta) < 0.05
                      ? "success"
                      : "exception"
                  }
                  strokeColor={
                    Math.abs(hedgeStatus.total_delta) < 0.05
                      ? "#52c41a"
                      : "#ff4d4f"
                  }
                  style={{ marginTop: 8 }}
                />
              </>
            )}
          </Card>
        </Col>
      </Row>

      {/* 第二行：Gamma Scalping 控制台 */}
      <Card
        title="Gamma Scalping 控制台 (P vs Q & Hedge Console)"
        style={{ marginBottom: 16 }}
        loading={loading}
      >
        {pqSpread && (
          <>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="P (市场隐含波动率)"
                  value={pqSpread.p_vol * 100}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: "#1890ff" }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="Q (模型预测波动率)"
                  value={pqSpread.q_vol * 100}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: "#52c41a" }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="P-Q 价差"
                  value={pqSpread.spread * 100}
                  precision={2}
                  suffix="%"
                  prefix={
                    pqSpread.spread > 0 ? (
                      <ArrowUpOutlined />
                    ) : (
                      <ArrowDownOutlined />
                    )
                  }
                  valueStyle={{
                    color: pqSpread.spread > 0 ? "#3f8600" : "#cf1322",
                  }}
                />
              </Col>
              <Col span={6}>
                <div>
                  <div style={{ marginBottom: 8 }}>交易信号</div>
                  <Tag
                    color={getSignalColor(pqSpread.signal)}
                    style={{ fontSize: 16 }}
                  >
                    {pqSpread.signal === "buy_volatility"
                      ? "做多波动率"
                      : "做空波动率"}
                  </Tag>
                  <div style={{ marginTop: 8 }}>
                    置信度: {(pqSpread.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={12}>
                <Card size="small" title="策略意图">
                  <div>
                    <strong>{pqSpread.intent_type || "保持观望"}</strong>
                  </div>
                  <div style={{ color: "#8c8c8c", marginTop: 4 }}>
                    {pqSpread.intent_reason || "暂无原因"}
                  </div>
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" title="宏观 / FOMO 状态">
                  <div>
                    宏观: {pqSpread.macro_regime || "unknown"} ·
                    强度 {(pqSpread.regime_score ?? 0).toFixed(2)}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    FOMO 指标: {(pqSpread.fomo_score ?? 0).toFixed(2)}
                  </div>
                </Card>
              </Col>
            </Row>
          </>
        )}
      </Card>

      {/* 第三行：组合 Greeks + 期权持仓明细 */}
      <Row gutter={16}>
        <Col span={10}>
          <Card title="投资组合 Greeks 细节" loading={loading}>
            {greeks && (
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="Delta"
                    value={greeks.total_delta}
                    precision={4}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Gamma"
                    value={greeks.total_gamma}
                    precision={4}
                  />
                </Col>
                <Col span={12} style={{ marginTop: 16 }}>
                  <Statistic
                    title="Vega"
                    value={greeks.total_vega}
                    precision={4}
                  />
                </Col>
                <Col span={12} style={{ marginTop: 16 }}>
                  <Statistic
                    title="Theta"
                    value={greeks.total_theta}
                    precision={4}
                  />
                </Col>
                <Col span={12} style={{ marginTop: 16 }}>
                  <Statistic
                    title="Rho"
                    value={greeks.total_rho}
                    precision={4}
                  />
                </Col>
                <Col span={12} style={{ marginTop: 16 }}>
                  <Tag
                    color={
                      greeks.hedge_status === "neutral" ? "green" : "orange"
                    }
                    icon={
                      <SyncOutlined spin={greeks.hedge_status !== "neutral"} />
                    }
                  >
                    {greeks.hedge_status === "neutral"
                      ? "Delta 中性"
                      : "需要对冲"}
                  </Tag>
                </Col>
              </Row>
            )}
          </Card>
        </Col>
        <Col span={14}>
          <Card title="期权持仓明细 (Options Book)" loading={loading}>
            <Table
              columns={positionColumns}
              dataSource={positions}
              rowKey="symbol"
              pagination={{ pageSize: 10 }}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default OptionsPanel;
