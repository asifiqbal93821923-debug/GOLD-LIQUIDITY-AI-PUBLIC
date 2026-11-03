#property strict
#property version   "1.01"
#property description "Pushes CLOSED XAUUSD candles from MT5 to Project Indicator App."

input string InpApiBaseUrl = "https://gold-terminal-api.onrender.com";
input string InpBridgeToken = "SET_THE_SAME_SERVER_MARKET_INGEST_TOKEN";
input string InpSymbol = "XAUUSD";
input int    InpBarsToSend = 300;
input int    InpTimerSeconds = 60;
input bool   InpSendM5 = true;
input bool   InpSendM15 = true;
input bool   InpSendH1 = true;
input bool   InpSendH4 = true;

string TfName(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M5:  return "5m";
      case PERIOD_M15: return "15m";
      case PERIOD_H1:  return "1h";
      case PERIOD_H4:  return "4h";
      case PERIOD_M3:  return "3m";
      case PERIOD_M30: return "30m";
      case PERIOD_D1:  return "1D";
      case PERIOD_M1:  return "1m";
   }
   return "";
}

bool SendTimeframe(ENUM_TIMEFRAMES tf)
{
   string tf_name=TfName(tf);
   if(tf_name=="") return false;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(InpSymbol,tf,1,InpBarsToSend,rates); // start_pos=1 excludes the forming candle
   if(copied<50)
   {
      Print("MT5 bridge: not enough closed candles for ",tf_name,", copied=",copied);
      return false;
   }

   int symbol_digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);
   string candles="[";
   for(int i=0;i<copied;i++)
   {
      if(i>0) candles+=",";
      candles+=StringFormat(
         "{\"time\":%I64d,\"open\":%s,\"high\":%s,\"low\":%s,\"close\":%s,\"volume\":%I64d}",
         (long)rates[i].time,
         DoubleToString(rates[i].open,symbol_digits),
         DoubleToString(rates[i].high,symbol_digits),
         DoubleToString(rates[i].low,symbol_digits),
         DoubleToString(rates[i].close,symbol_digits),
         (long)rates[i].tick_volume
      );
   }
   candles+="]";
   string body=StringFormat("{\"symbol\":\"XAUUSD\",\"timeframe\":\"%s\",\"source\":\"mt5_bridge\",\"candles\":%s}",tf_name,candles);
   string headers="Content-Type: application/json\r\nX-Bridge-Token: "+InpBridgeToken+"\r\n";
   char post_data[],result[];
   StringToCharArray(body,post_data,0,WHOLE_ARRAY,CP_UTF8);
   if(ArraySize(post_data)>0) ArrayResize(post_data,ArraySize(post_data)-1);
   string response_headers;
   ResetLastError();
   int status=WebRequest("POST",InpApiBaseUrl+"/api/market/candles/bridge",headers,10000,post_data,result,response_headers);
   if(status==-1)
   {
      Print("MT5 bridge WebRequest failed. Error=",GetLastError(),
            ". Add the API host to MT5 Tools > Options > Expert Advisors > Allow WebRequest.");
      return false;
   }
   string response=CharArrayToString(result,0,-1,CP_UTF8);
   if(status<200 || status>=300)
   {
      Print("MT5 bridge HTTP ",status,": ",response);
      return false;
   }
   Print("MT5 bridge OK ",tf_name," candles=",copied," response=",response);
   return true;
}


bool SendQuote()
{
   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol,tick))
   {
      Print("MT5 bridge: no broker tick for ",InpSymbol,". Check Market Watch and symbol trading session.");
      return false;
   }
   double bid=tick.bid;
   double ask=tick.ask;
   double point=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);
   if(bid<=0 || ask<bid || point<=0 || tick.time_msc<=0)
   {
      Print("MT5 bridge: invalid quote fields for ",InpSymbol);
      return false;
   }
   int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);
   long tick_epoch=(long)(tick.time_msc/1000);
   string body=StringFormat("{\"symbol\":\"XAUUSD\",\"time\":%I64d,\"bid\":%s,\"ask\":%s,\"point\":%s}",
      tick_epoch,DoubleToString(bid,digits),DoubleToString(ask,digits),DoubleToString(point,10));
   string headers="Content-Type: application/json\r\nX-Bridge-Token: "+InpBridgeToken+"\r\n";
   char post_data[],result[];
   StringToCharArray(body,post_data,0,WHOLE_ARRAY,CP_UTF8);
   if(ArraySize(post_data)>0) ArrayResize(post_data,ArraySize(post_data)-1);
   string response_headers;
   ResetLastError();
   int status=WebRequest("POST",InpApiBaseUrl+"/api/market/quote/bridge",headers,10000,post_data,result,response_headers);
   if(status<200 || status>=300)
   {
      Print("MT5 quote bridge HTTP ",status," error=",GetLastError()," response=",CharArrayToString(result,0,-1,CP_UTF8));
      return false;
   }
   Print("MT5 quote bridge OK spread_points=",DoubleToString((ask-bid)/point,2));
   return true;
}

void PushAll()
{
   if(InpSendH4)  SendTimeframe(PERIOD_H4);
   if(InpSendH1)  SendTimeframe(PERIOD_H1);
   if(InpSendM15) SendTimeframe(PERIOD_M15);
   if(InpSendM5)  SendTimeframe(PERIOD_M5);
   SendQuote();
}

int OnInit()
{
   if(StringLen(InpApiBaseUrl)<8 || InpBarsToSend<50 || InpTimerSeconds<15)
   {
      Print("Set a valid API URL, at least 50 candles, and timer >= 15 seconds.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpBridgeToken=="SET_THE_SAME_SERVER_MARKET_INGEST_TOKEN" || StringLen(InpBridgeToken)<16)
   {
      Print("Set a strong InpBridgeToken matching the server MARKET_INGEST_TOKEN (at least 16 characters).");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!SymbolSelect(InpSymbol,true))
   {
      Print("Could not select symbol ",InpSymbol,". Check your broker's Gold symbol name.");
      return INIT_FAILED;
   }
   EventSetTimer(MathMax(15,InpTimerSeconds));
   PushAll();
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   PushAll();
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}
