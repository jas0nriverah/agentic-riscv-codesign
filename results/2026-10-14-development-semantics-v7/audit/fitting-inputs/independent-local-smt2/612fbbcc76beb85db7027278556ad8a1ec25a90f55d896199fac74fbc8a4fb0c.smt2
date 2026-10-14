(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(assert
 (let ((?x703 (bvshl (bvadd (_ bv0 32) (_ bv0 32)) (bvand (_ bv20 32) (_ bv31 32)))))
(and (distinct (_ bv0 32) ?x703) true)))
(check-sat)
