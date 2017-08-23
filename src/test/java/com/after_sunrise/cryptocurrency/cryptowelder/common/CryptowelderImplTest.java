package com.after_sunrise.cryptocurrency.cryptowelder.common;

import com.after_sunrise.cryptocurrency.cryptowelder.Cryptowelder;
import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.Injector;
import org.testng.annotations.Test;

import java.util.concurrent.CountDownLatch;

import static java.util.concurrent.TimeUnit.SECONDS;
import static org.testng.Assert.assertTrue;

/**
 * @author takanori.takase
 * @version 0.0.1
 */
public class CryptowelderImplTest {

    @Test
    public void testModule() throws Exception {

        Injector injector = Guice.createInjector(new CryptowelderImpl.Module());

        Cryptowelder target = injector.getInstance(Cryptowelder.class);

        try {

            // Do not call "run()"

        } finally {

            target.close();

        }

    }

    @Test
    public void testRun() throws Exception {

        CountDownLatch latch = new CountDownLatch(1);

        CryptowelderImpl target = new CryptowelderImpl(Guice.createInjector(new AbstractModule() {
            @Override
            protected void configure() {

                bind(CountDownLatch.class).toInstance(latch);

            }
        }));

        try {

            target.run();

        } finally {

            target.close();

        }

        assertTrue(latch.await(1, SECONDS));

    }

}
