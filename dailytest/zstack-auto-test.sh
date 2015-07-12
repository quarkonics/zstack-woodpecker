#!/bin/bash
export PATH=$PATH:/bin:/sbin:/usr/bin:/usr/sbin
#export JAVA_HOME=/usr/lib/jvm/java-1.7.0-openjdk-1.7.0.3.x86_64
#export CATALINA_OPTS="-Djava.net.preferIPv4Stack=true"
#export ZSTACK_MANAGEMENT_SERVER_PASSWORD=1
#read global proxy for possible external connection like salt. make sure all zstack hosts ip should be listed in $no_proxy, otherwise the testing will be failure when doing vm.check(), since testagent will use http protocol to check vm status.
#[ -f ${PWD}/.proxyrc ] && source ${PWD}/.proxyrc
#[ -f ~/.zstackwoodpecker/.proxyrc ] && source ~/.zstackwoodpecker/.proxyrc

#avoid of using http_proxy to impact zstack HTTP API request. 
#the http_proxy and https_proxy might be used for pip installation.
#[ ! -z $http_proxy ] && export woodpecker_http_proxy=$http_proxy
#[ ! -z $https_proxy ] && export woodpecker_https_proxy=$https_proxy

ZSTACK_TEST_ROOT=${ZSTACK_TEST_ROOT-'/usr/local/zstack'}

help(){
    echo "Usage: 
        $0 [options]
        zstack-auto-test will automatically build, install and test zstack. It
        will also finally report the result to github.

Options:
  -t [unittest/integrationtest/all/anything]
                [Optional] Define test type. If not providing type, it will only
                run the default integration test, when there is new zstack 
                commit. If set 'unittest' or 'integrationtest', it will run 
                related test, no matter if there is new commit or not. If set 
                'ANYTHING' rather than 'unittest' or 'integrationtest', it will
                run both unittest and integration test, no matter if there is 
                new zstack commit. 
  -r TEST_ROOT_PATH
                set zstack test 'root' path, which include zstack, zstack-utilty
                , zstack-woodpecker etc. The default value is $ZSTACK_TEST_ROOT
  -n            run zstack integration test without build zstack source
  -d            enable ZStack debug option:
                -Xdebug -Xnoagent -Djava.compiler=NONE -Xrunjdwp:transport=
                dt_socket,server=y,suspend=y,address=5005
  -h            show this message and exit.
"
    exit
}

SKIP_BUILD=1

OPTIND=1
while getopts "t:r:hnd" Option
do
    case $Option in
        r ) ZSTACK_TEST_ROOT=$OPTARG;;
        t ) TEST_TYPE=$OPTARG;;
        d ) CATALINA_OPTS=$CATALINA_OPTS" -Xdebug -Xnoagent -Djava.compiler=NONE -Xrunjdwp:transport=dt_socket,server=y,suspend=y,address=5005";;
        h ) help;;
        n ) SKIP_BUILD=0 ;;
        * ) help;;
    esac
done
OPTIND=1

export ZSTACK_TEST_ROOT=$ZSTACK_TEST_ROOT

ZSTACK_FOLDER="$ZSTACK_TEST_ROOT/zstack"
ZSTACK_UTILITY_FOLDER="$ZSTACK_TEST_ROOT/zstack-utility"
ZSTACK_WOODPECKER_FOLDER="$ZSTACK_TEST_ROOT/zstack-woodpecker"
ZSTACK_TEST_FOLDER="${ZSTACK_WOODPECKER_FOLDER}/dailytest"
DAILY_TEST_FOLDER=${ZSTACK_WOODPECKER_FOLDER}/dailytest
unit_test_log="/tmp/zstack/zstack_unit_test_log"
unit_test_result="/tmp/zstack/zstack_unit_test_result"
unit_test_last_result="/tmp/zstack/zstack_unit_test_last_result"
ZSTACK_TEST_TMP_FOLDER=/tmp/zstack
integration_test_log=${ZSTACK_TEST_TMP_FOLDER}/zstack_integration_test.log
NEED_REPORT="NO"
TEST_LOCK=${ZSTACK_TEST_TMP_FOLDER}/.zstack_test_lock
SANITYTEST_CONF_FOLDER="$ZSTACK_TEST_ROOT/sanitytest"
BUILD_ZSTACK_SCRIPT=$DAILY_TEST_FOLDER/build_zstack.sh
DEPLOY_ZSTACK_SCRIPT=$DAILY_TEST_FOLDER/deploy_zstack.sh
ZSTACK_ARCHIVE=$ZSTACK_TEST_ROOT/zstack_build_archive
GITHUB_COMMENTS_POST=/tmp/zstack/github_comments_post.sh

Exit(){
    rm -f $TEST_LOCK
    if [ $1 -eq 0 ]; then
        echo -e "$(tput setaf 2)\n\t -- zstack auto test executed successfully -- \n $(tput sgr0)"
    else
        echo -e "$(tput setaf 1)\n\t -- zstack auto test executed FAIL -- \n $(tput sgr0)"
    fi
    exit $1
}

trap "echo receive termination signal; rm $TEST_LOCK; exit 1" SIGINT SIGTERM

get_commit(){
    git log -1|grep commit|awk '{print $2}'
}

build_and_prepare_zstack(){
    [ $SKIP_BUILD -eq 0 ] && echo ' - Skip zstack building - ' && return
    #$DEPLOY_ZSTACK_SCRIPT
    cd $ZSTACK_TEST_FOLDER
    ./zstest.py -b
    if [ $? -ne 0 ]; then
        echo "build ZStack meet failure"
        commit_report 'Fail' 'Build zstack or deploy zstack.war meet failure. Please check.'
        Exit 1
    fi
    rm -rf $SANITYTEST_CONF_FOLDER
    mkdir -p $SANITYTEST_CONF_FOLDER
    tar zxvf $ZSTACK_ARCHIVE/latest -C $SANITYTEST_CONF_FOLDER
}

test_zstack_unit_test(){
    cd $ZSTACK_FOLDER
    #build zstack
    echo -e "\nBuild and install zstack for unit test"
    mvn -DskipTests clean install 2>&1 >/dev/null
    if [ $? -ne 0 ]; then
        commit_report 'Fail' 'Build zstack failure. Please check.'
        Exit 1
    fi
    echo -e "$(tput setaf 2) \n\t\t... pass$(tput sgr0)"
    cd test
    echo "Begin run zstack unit test"
    mvn test -Dtest=UnitTestSuite| tee $unit_test_log
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "Unit test run complete. Check result"
    else
        commit_report 'Fail' "zstack unit test execution failure. Please check."
        Exit 1
    fi

    failed_case=`grep "Total cases" $unit_test_log |awk -F 'Failed:' '{print $2}'|awk '{print $1}'`
    test_summary_line=`grep -n "Test Summary" $unit_test_log|awk -F: '{print $1}'`
    if [ $failed_case -eq 0 ];then
        test_result=`sed -n "${test_summary_line},\\$p" $unit_test_log|sed "s/'//g"`
        sed -n "${test_summary_line},\\$p" $unit_test_log|sed "s/'//g" > $unit_test_last_result
        sed -i 's/------------------------------------------------------------------------/\\n/g' $test_result
        sed -i 's/-------//g' $test_result
        commit_report 'Pass' "Unit test result: $test_result"
    else
        fail_case_log_line=`grep -n "Failed cases' log" $unit_test_log|awk -F: '{print $1}'`
        test_result=`sed -n "${fail_case_log_line},\\$p" $unit_test_log|sed "s/'//g"`
        tempfile=`mktemp`
        echo $test_result > $tempfile
        /bin/cp -f $tempfile $unit_test_result
        sed -i 's/------------------------------------------------------------------------/\n/g' $tempfile
        sed -i 's/-------//g' $tempfile
        /bin/cp -f $tempfile $unit_test_result
        sed -i ':q;N;s/\n/\\n/g;t q' $tempfile
        commit_report 'Fail' "Unit test result: `cat $tempfile`"
    fi
    diff -b -B $unit_test_last_result $unit_test_result | grep '^[<>]' | sed -e 's/^</--/' -e 's/^>/++/'> $tempfile
    sed -i ':q;N;s/\n/\\n/g;t q' $tempfile
    commit_report 'Comments' "Diff with last test result: \\n`cat $tempfile`"
    rm -f $tempfile
    #Exit 0
}

test_zstack_integration_test(){
    echo " - Execute Integration Test"
    unset http_proxy
    unset https_proxy
    #cd $ZSTACK_UTILITY_FOLDER
    #old_utility_commit=`get_commit`
    #echo -e "Git pull latest zstack-utility"
    #git pull >/dev/null
    #if [ $? -ne 0 ];then
    #    echo "git pull failure. Exit".
    #    Exit 1
    #fi
    #new_utility_commit=`get_commit`
    #echo -e "\t\t... ... latest commit: $new_utility_commit \n"
    #cd zstackbuild
    #echo -e "Build zstack.war"
    #ant all >/dev/null
    #if [ $? -ne 0 ]; then
    #    commit_report 'Fail' "zstack utility and zstack.war build failure"
    #    Exit 1
    #fi
    #echo -e "\t\t... ... build pass. \n"

    #TODO: need reinstall zstacklib and apibinding
    #/bin/cp -f target/zstack.war $SANITYTEST_CONF_FOLDER
    cd $ZSTACK_TEST_FOLDER
    echo "Execute integration test"
    #zstack-woodpecker -f sanity_test.xml >/tmp/zstack_integration_test.log
    #Crontab might meet problem without -v option.
    #zstack-woodpecker -f sanity_test.xml |tee $integration_test_log
    ./zstest.py -s b,v

    if [ ${PIPESTATUS[0]} -ne 0 ];then
        commit_report 'Fail' "zstack-woodpecker execution failure. Please check."
        Exit 1
    fi

    # check test result.
    echo "\nTest Summary:\n\n" > config_xml/test-result/latest/summary-commit
    echo "TestSuite|TestCase | Pass | Fail | TIMEOUT | Skip\n" >> config_xml/test-result/latest/summary-commit
    echo "---------|---------| ---- | ---- | ------- | ----\n" >> config_xml/test-result/latest/summary-commit
    cat config_xml/test-result/latest/summary | sed -n '/--*$/{:1;N;/--*$/{p;b};N;b1}' | grep -v '\-\-' | awk '{if ($1~/:/) {suite=$1;gsub(":","", suite)} else {if ($2!=1) {printf("%s|__%s__|%s|%s|%s|%s\\n", suite, $1, $2, $3, $4, $5)} else {printf("%s|%s|%s|%s|%s|%s\\n", suite, $1, $2, $3, $4, $5)}}}' >> config_xml/test-result/latest/summary-commit
    cat config_xml/test-result/latest/summary | grep "Total:" | awk '{printf("Total|%s|%s|%s|%s|%s\n",$2,$3,$4,$5,$6)}' >> config_xml/test-result/latest/summary-commit
    commit_report 'Pass' "Integration Test Result: `cat config_xml/test-result/latest/summary-commit`"

    Exit 0
}

commit_report(){
    echo $2
    if [ $1 == 'Pass' ];then
        comment_body="#[zstack Test Bot Report]        P A S S \n $2"
    elif [ $1 == 'Fail' ]; then
        comment_body="#[zstack Test Bot Report]        F A I L \n $2"
    else
        comment_body="#[zstack Test Bot Report]        Comments \n $2"
    fi
    curl_command="curl -d '{\"body\": \" $comment_body \"}' -i -u zstacktest:zstack@test1 -X POST https://api.github.com/repos/zstacktest/zstack/commits/$new_commit/comments"
    echo $curl_command > $GITHUB_COMMENTS_POST
    [ -f ~/.zstackwoodpecker/.proxyrc ] && source ~/.zstackwoodpecker/.proxyrc
    sh $GITHUB_COMMENTS_POST
}

if [ -f $TEST_LOCK ];then
    echo "Can't get test lock: $TEST_LOCK. It is mostly because a testing is runing"
    exit 2
fi

wrong_root(){
    echo "Please provide correct ZSTACK_TEST_ROOT parameter through -r option!"
}

pull_source() {
    ret=1

    cd $ZSTACK_FOLDER
    old_commit=`get_commit`
    echo -e "\n - Check and pull latest zstack source code - \n"
    echo "    Current ZStack commit: $old_commit"
    git pull >/dev/null
    if [ $? -ne 0 ];then
        echo "git pull failure. Exit".
        Exit 1
    fi
    new_commit=`get_commit`
    echo "    Latest ZStack commit: $new_commit\n"

    if [ $new_commit != $old_commit ]; then
        ret=0
    fi

    cd $ZSTACK_UTILITY_FOLDER
    old_commit=`get_commit`
    echo -e "\n - Check and pull latest zstack-utility source code - \n"
    echo "    Current zStack-utility commit: $old_commit"
    git pull >/dev/null
    if [ $? -ne 0 ];then
        echo "git pull failure. Exit".
        Exit 1
    fi
    new_commit2=`get_commit`
    echo "    Latest zStack-utility commit: $new_commit\n"

    #if [ $new_commit2 != $old_commit ]; then
    #    ret=0
    #fi

    return $ret
}

if [ ! -d $ZSTACK_FOLDER ] ; then
    echo "Did not find $ZSTACK_FOLDER for ZStack source code."
    wrong_root
    exit 1
fi

if [ ! -d $ZSTACK_WOODPECKER_FOLDER ] ; then
    echo "Did not find $ZSTACK_WOODPECKER_FOLDER for holding ZStack-woodpecker source code."
    wrong_root
    exit 1
fi

if [ ! -d $ZSTACK_UTILITY_FOLDER ] ; then
    echo "Did not find $ZSTACK_UTILITY_FOLDER for ZStack-utility source code."
    wrong_root
    exit 1
fi

mkdir -p $ZSTACK_TEST_TMP_FOLDER
touch $TEST_LOCK

current_folder=`pwd`
if [ $SKIP_BUILD -eq 1 ]; then
    pull_source
    has_new_source=$?
fi

if [ -z $TEST_TYPE ]; then
    if [ $SKIP_BUILD -eq 0 ] || [ $has_new_source -ne 0 ]; then
        echo "Do not build zstack"
        test_zstack_integration_test
    else
        [ -f $unit_test_result ] && mv $unit_test_result $unit_test_last_result
        build_and_prepare_zstack
        test_zstack_integration_test
    fi
elif [ $TEST_TYPE = 'unittest' ]; then
    [ -f $unit_test_result ] && mv $unit_test_result $unit_test_last_result
    build_and_prepare_zstack
    test_zstack_unit_test
elif [ $TEST_TYPE = 'integrationtest' ];then
    build_and_prepare_zstack
    test_zstack_integration_test
else
    build_and_prepare_zstack
    test_zstack_unit_test
    test_zstack_integration_test
fi

Exit 3
