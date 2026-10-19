(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x24 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv2304 32))))
(let ((?x305 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x23 (bvshl (bvadd independent_opaque_0 (_ bv576 32)) ?x305)))
(and (distinct ?x23 ?x24) true)))))
(check-sat)
