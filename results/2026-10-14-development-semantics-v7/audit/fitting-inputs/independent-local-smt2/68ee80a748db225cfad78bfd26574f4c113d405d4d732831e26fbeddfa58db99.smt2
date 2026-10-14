(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x24 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv2304 32))))
(let ((?x47 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x1227 (bvshl (bvadd independent_opaque_0 (_ bv576 32)) ?x47)))
(and (distinct ?x1227 ?x24) true)))))
(check-sat)
