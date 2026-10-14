(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x23 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4294967292 32))))
(let ((?x34 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x573 (bvshl (bvadd independent_opaque_0 (_ bv4294967295 32)) ?x34)))
(and (distinct ?x573 ?x23) true)))))
(check-sat)
