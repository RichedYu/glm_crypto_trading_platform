import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

export interface PQSpreadData {
  underlying: string;
  p_vol: number;
  q_vol: number;
  spread: number;
  signal: string;
  confidence: number;
  intent_type?: string;
  intent_reason?: string;
  macro_regime?: string;
  regime_score?: number;
  fomo_score?: number;
  timestamp: string;
}

export interface PortfolioGreeks {
  total_delta: number;
  total_gamma: number;
  total_vega: number;
  total_theta: number;
  total_rho: number;
  timestamp: string;
  hedge_status: string;
}

export interface OptionPosition {
  symbol: string;
  quantity: number;
  avg_price: number;
  unrealized_pnl: number;
  greeks: {
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
    rho?: number;
  };
  strategy_id: string;
}

export interface HedgeStatus {
  total_delta: number;
  status: string;
  recommended_action: string;
  hedge_quantity: number;
  timestamp: string;
}

export interface VolatilitySurface {
  underlying: string;
  atm_iv: number;
  timestamp: string;
  surface_data: Array<{
    strike: number;
    expiry: string;
    call_iv: number;
    put_iv: number;
    call_price: number;
    put_price: number;
  }>;
}

export interface StrategyState {
  strategy_id: string;
  status: string;
  [key: string]: any;
}

class OptionsApiService {
  /**
   * 获取P-Q波动率价差
   */
  async getPQSpread(underlying: string = "BTC/USDT"): Promise<PQSpreadData> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/pq-spread/${underlying}`
    );
    return response.data;
  }

  /**
   * 获取投资组合Greeks
   */
  async getPortfolioGreeks(): Promise<PortfolioGreeks> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/greeks/portfolio`
    );
    return response.data;
  }

  /**
   * 获取期权持仓
   */
  async getOptionPositions(): Promise<{
    positions: OptionPosition[];
    total_count: number;
  }> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/positions/options`
    );
    return response.data;
  }

  /**
   * 获取Delta对冲状态
   */
  async getHedgeStatus(): Promise<HedgeStatus> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/hedge/status`
    );
    return response.data;
  }

  /**
   * 获取波动率曲面
   */
  async getVolatilitySurface(
    underlying: string = "BTC/USDT"
  ): Promise<VolatilitySurface> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/volatility-surface/${underlying}`
    );
    return response.data;
  }

  /**
   * 获取P vs Q策略状态
   */
  async getPQTraderState(): Promise<StrategyState> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/strategies/pq-trader/state`
    );
    return response.data;
  }

  /**
   * 获取Delta对冲策略状态
   */
  async getDeltaHedgerState(): Promise<StrategyState> {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/options/strategies/delta-hedger/state`
    );
    return response.data;
  }
}

export const optionsApi = new OptionsApiService();
