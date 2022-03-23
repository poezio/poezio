use std::str::FromStr;
use chrono::{DateTime, Utc, TimeZone};
use nom;
use nom::{
    IResult,
    sequence::tuple,
    bytes::complete::{tag, take, take_until},
    combinator::{map, map_res},
    multi::many_m_n,
};

pub trait LogItem {
    fn get_time(&self) -> &DateTime<Utc>;
    fn get_message(&self) -> String;
}

#[derive(Debug, PartialEq)]
pub struct LogInfo<'a> {
    time: DateTime<Utc>,
    message: Vec<&'a str>,
}

impl<'a> LogItem for LogInfo<'a> {
    fn get_time(&self) -> &DateTime<Utc> {
        &self.time
    }

    fn get_message(&self) -> String {
        self.message.join("\n")
    }
}

#[derive(Debug, PartialEq)]
pub struct LogMessage<'a> {
    time: DateTime<Utc>,
    nick: &'a str,
    message: Vec<&'a str>,
}

impl<'a> LogMessage<'a> {
    pub fn get_nick(&self) -> &str {
        self.nick
    }
}

impl<'a> LogItem for LogMessage<'a> {
    fn get_time(&self) -> &DateTime<Utc> {
        &self.time
    }

    fn get_message(&self) -> String {
        self.message.join("\n")
    }
}

pub fn parse_datetime(i: &str) -> IResult<&str, DateTime<Utc>> {
    let (i, (year, month, day, _, hour, _, minute, _, second, _)) = tuple((
        map_res(take(4usize), i32::from_str),
        map_res(take(2usize), u32::from_str),
        map_res(take(2usize), u32::from_str),
        tag("T"),
        map_res(take(2usize), u32::from_str),
        tag(":"),
        map_res(take(2usize), u32::from_str),
        tag(":"),
        map_res(take(2usize), u32::from_str),
        tag("Z"),
    ))(i)?;
    Ok((i, Utc.ymd(year, month, day).and_hms(hour, minute, second)))
}

pub fn parse_log_info(i: &str) -> IResult<&str, LogInfo> {
    let (i, (_, time, _, nb_lines)) = tuple((
        tag("MI "),
        parse_datetime,
        tag(" "),
        map_res(take(3usize), usize::from_str),
    ))(i)?;
    let (i, message) = many_m_n(nb_lines + 1, nb_lines + 1, map(tuple((
        tag(" "),
        take_until("\n"),
        tag("\n"),
    )), |(_, line, _)| line))(i)?;
    Ok((i, LogInfo {
        time,
        message,
    }))
}

pub fn parse_log_message(i: &str) -> IResult<&str, LogMessage> {
    let (i, (_, time, _, nb_lines, _, nick, _, line0, _)) = tuple((
        tag("MR "),
        parse_datetime,
        tag(" "),
        map_res(take(3usize), usize::from_str),
        tag(" <"),
        take_until(">  "),
        tag(">  "),
        take_until("\n"),
        tag("\n"),
    ))(i)?;
    let (i, lines) = many_m_n(nb_lines, nb_lines, map(tuple((
        tag(" "),
        take_until("\n"),
        tag("\n"),
    )), |(_, line, _)| line))(i)?;
    Ok((i, LogMessage {
        time,
        nick,
        message: {
            let mut message = lines;
            message.insert(0, line0);
            message
        }
    }))
}

#[derive(Debug, PartialEq)]
pub enum Item<'a> {
    Message(LogMessage<'a>),
    Info(LogInfo<'a>),
}

pub fn parse_logs(mut logs: &str) -> IResult<&str, Vec<Item>> {
    let mut items = vec![];
    loop {
        if logs.is_empty() {
            break;
        }
        if logs.starts_with("MR ") {
            let message = parse_log_message(logs)?;
            logs = message.0;
            items.push(Item::Message(message.1));
        } else if logs.starts_with("MI ") {
            let info = parse_log_info(logs)?;
            logs = info.0;
            items.push(Item::Info(info.1));
        } else {
            return Err(nom::Err::Error(nom::error::Error::new(logs, nom::error::ErrorKind::Fail)));
        }
    }
    Ok((logs, items))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn simple_message() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello world!\n";
        let message = LogMessage {
            time: "2018-10-16T16:10:08+0200".parse().unwrap(),
            nick: "Link Mauve",
            message: vec!["Hello world!"],
        };
        let (_, message2) = parse_log_message(log).unwrap();
        assert_eq!(message, message2);
    }

    #[test]
    fn multiple_messages() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello…\nMR 20181016T14:10:11Z 000 <Link Mauve>  world!\n";
        let messages = [
            LogMessage {
                time: "2018-10-16T16:10:08+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["Hello…"],
            },
            LogMessage {
                time: "2018-10-16T16:10:11+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["world!"],
            }
        ];
        let (i, message1) = parse_log_message(log).unwrap();
        let (_, message2) = parse_log_message(i).unwrap();
        assert_eq!(messages, [message1, message2]);
    }

    #[test]
    fn parse_all_logs() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello…\nMR 20181016T14:10:11Z 000 <Link Mauve>  world!\n";
        let messages = vec![
            Item::Message(LogMessage {
                time: "2018-10-16T16:10:08+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["Hello…"],
            }),
            Item::Message(LogMessage {
                time: "2018-10-16T16:10:11+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["world!"],
            })
        ];
        let (_, messages1) = parse_logs(log).unwrap();
        assert_eq!(messages, messages1);
    }

    #[test]
    fn trailing_characters() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello…\nMR 20181016T14:10:11Z 000 <Link Mauve>  world!\n\n";
        parse_logs(log).unwrap_err();
    }

    #[test]
    fn multiline_message() {
        let log = "MR 20181016T14:10:08Z 001 <Link Mauve>  Hello…\n world!\n";
        let message = LogMessage {
            time: "2018-10-16T16:10:08+0200".parse().unwrap(),
            nick: "Link Mauve",
            message: vec!["Hello…", "world!"],
        };
        let (_, message2) = parse_log_message(log).unwrap();
        assert_eq!(message, message2);
    }
}
