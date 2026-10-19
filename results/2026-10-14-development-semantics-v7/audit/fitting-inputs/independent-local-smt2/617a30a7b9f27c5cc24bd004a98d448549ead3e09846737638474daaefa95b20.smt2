(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1208 (bvadd (bvshl independent_opaque_0 (bvand (_ bv4 32) (_ bv31 32))) (_ bv4294967280 32))))
(let ((?x84 (bvand (_ bv4 32) (_ bv31 32))))
(let ((?x676 (bvshl (bvadd independent_opaque_0 (_ bv4294967295 32)) ?x84)))
(and (distinct ?x676 ?x1208) true)))))
(check-sat)
