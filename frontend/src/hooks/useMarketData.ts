import { useEffect, useState, useRef } from "react";
import { wsService } from "../services/websocket";

export const useMarketData = <T>(eventType: string, initialState?: T) => {
  const [data, setData] = useState<T | undefined>(initialState);
  // 使用 ref 来避免闭包问题，尽管这里主要是状态更新
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;

    const unsubscribe = wsService.subscribe(eventType, (payload) => {
      if (isMounted.current) {
        setData(payload as T);
      }
    });

    return () => {
      isMounted.current = false;
      unsubscribe();
    };
  }, [eventType]);

  return data;
};
