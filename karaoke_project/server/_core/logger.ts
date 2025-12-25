/**
 * Sistema de logging para capturar erros e eventos
 */

interface LogEntry {
  timestamp: Date;
  level: 'error' | 'warn' | 'info';
  message: string;
  details?: any;
}

class Logger {
  private logs: LogEntry[] = [];
  private maxLogs = 100; // Manter apenas os últimos 100 logs

  log(level: 'error' | 'warn' | 'info', message: string, details?: any) {
    const entry: LogEntry = {
      timestamp: new Date(),
      level,
      message,
      details,
    };

    this.logs.push(entry);

    // Manter apenas os últimos maxLogs
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }

    // Log no console também
    const prefix = `[${level.toUpperCase()}]`;
    if (level === 'error') {
      console.error(prefix, message, details);
    } else if (level === 'warn') {
      console.warn(prefix, message, details);
    } else {
      console.log(prefix, message, details);
    }
  }

  error(message: string, details?: any) {
    this.log('error', message, details);
  }

  warn(message: string, details?: any) {
    this.log('warn', message, details);
  }

  info(message: string, details?: any) {
    this.log('info', message, details);
  }

  getLogs(limit: number = 50): LogEntry[] {
    return this.logs.slice(-limit);
  }

  getErrorLogs(limit: number = 50): LogEntry[] {
    return this.logs.filter(log => log.level === 'error').slice(-limit);
  }

  clear() {
    this.logs = [];
  }
}

export const logger = new Logger();
